"""Neo4j-backed LangGraph checkpointer (PHASE3 §5-3).

Why: PHASE2 used ``SqliteSaver`` — a local file. That needs a long-lived process
with a persistent disk; on a free serverless host the disk is ephemeral and a
cold start between the ``interrupt()`` and the ``Command(resume=...)`` would lose
the paused agent. Neo4j Aura is an always-on managed store, so moving the
checkpoint there removes the local-disk requirement and lets the agent resume
across a *process boundary* (the exact shape of a stateless HTTP run→dispatch).

Design (matches the plan's node model — one blob per checkpoint):
  (:AgentCheckpoint {uid, thread_id, checkpoint_ns, checkpoint_id,
                     parent_checkpoint_id, ts, type, checkpoint_blob,
                     metadata_type, metadata_blob})
  (:AgentCheckpointWrite {uid, thread_id, checkpoint_ns, checkpoint_id,
                          task_id, idx, channel, type, blob, task_path})

Unlike ``InMemorySaver``/the Postgres saver we do **not** split ``channel_values``
into a deduped blobs table — we serialise the whole checkpoint into one
``checkpoint_blob`` (Base64 of the LangGraph serializer output). Simpler, matches
the plan's single-blob node, and the agent state here is small.

``uid`` is a single synthetic key (``thread_id|ns|checkpoint_id``) so MERGE needs
only a single-property uniqueness constraint — no Enterprise-only composite/node-key
constraint required.
"""
from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)

from . import config as _cfg, db

_CP_UID = "{tid}\x1f{ns}\x1f{cid}"
_W_UID = "{tid}\x1f{ns}\x1f{cid}\x1f{task}\x1f{idx}"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


class Neo4jCheckpointSaver(BaseCheckpointSaver):
    """A LangGraph checkpointer persisting to Neo4j via the shared db.driver()."""

    def __init__(self, *, serde=None) -> None:
        super().__init__(serde=serde)

    # ── one-time DDL (idempotent; also lives in schema.cypher) ────────────────
    @staticmethod
    def setup() -> None:
        with db.driver().session(database=_cfg.NEO4J_DATABASE) as s:
            s.run(
                "CREATE CONSTRAINT agent_checkpoint_uid IF NOT EXISTS "
                "FOR (n:AgentCheckpoint) REQUIRE n.uid IS UNIQUE"
            ).consume()
            s.run(
                "CREATE CONSTRAINT agent_checkpoint_write_uid IF NOT EXISTS "
                "FOR (w:AgentCheckpointWrite) REQUIRE w.uid IS UNIQUE"
            ).consume()

    # ── sync API ──────────────────────────────────────────────────────────────
    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        cfg = config["configurable"]
        tid, ns = cfg["thread_id"], cfg.get("checkpoint_ns", "")
        cid = checkpoint["id"]
        cp_type, cp_bytes = self.serde.dumps_typed(checkpoint)
        md_type, md_bytes = self.serde.dumps_typed(
            get_checkpoint_metadata(config, metadata)
        )
        props = {
            "uid": _CP_UID.format(tid=tid, ns=ns, cid=cid),
            "thread_id": tid,
            "checkpoint_ns": ns,
            "checkpoint_id": cid,
            "parent_checkpoint_id": cfg.get("checkpoint_id"),
            "ts": checkpoint.get("ts"),
            "type": cp_type,
            "checkpoint_blob": _b64(cp_bytes),
            "metadata_type": md_type,
            "metadata_blob": _b64(md_bytes),
        }
        with db.driver().session(database=_cfg.NEO4J_DATABASE) as s:
            s.run(
                "MERGE (n:AgentCheckpoint {uid:$uid}) SET n += $props",
                uid=props["uid"], props=props,
            ).consume()
        return {"configurable": {"thread_id": tid, "checkpoint_ns": ns, "checkpoint_id": cid}}

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        cfg = config["configurable"]
        tid, ns, cid = cfg["thread_id"], cfg.get("checkpoint_ns", ""), cfg["checkpoint_id"]
        rows = []
        for idx, (channel, value) in enumerate(writes):
            widx = WRITES_IDX_MAP.get(channel, idx)
            v_type, v_bytes = self.serde.dumps_typed(value)
            rows.append({
                "uid": _W_UID.format(tid=tid, ns=ns, cid=cid, task=task_id, idx=widx),
                "thread_id": tid, "checkpoint_ns": ns, "checkpoint_id": cid,
                "task_id": task_id, "idx": widx, "channel": channel,
                "type": v_type, "blob": _b64(v_bytes), "task_path": task_path,
                "overwrite": widx < 0,  # special channels upsert; regular writes insert-once
            })
        with db.driver().session(database=_cfg.NEO4J_DATABASE) as s:
            # ON CREATE always sets; ON MATCH only when this is a special (negative-idx)
            # channel, mirroring InMemorySaver's "skip if already present" for idx>=0.
            s.run(
                "UNWIND $rows AS r "
                "MERGE (w:AgentCheckpointWrite {uid:r.uid}) "
                "ON CREATE SET w += r "
                "ON MATCH SET w += (CASE WHEN r.overwrite THEN r ELSE {} END)",
                rows=rows,
            ).consume()

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        cfg = config["configurable"]
        tid, ns = cfg["thread_id"], cfg.get("checkpoint_ns", "")
        cid = get_checkpoint_id(config)
        with db.driver().session(database=_cfg.NEO4J_DATABASE) as s:
            if cid:
                rec = s.run(
                    "MATCH (n:AgentCheckpoint {thread_id:$tid, checkpoint_ns:$ns, checkpoint_id:$cid}) "
                    "RETURN n LIMIT 1", tid=tid, ns=ns, cid=cid,
                ).single()
            else:
                rec = s.run(
                    "MATCH (n:AgentCheckpoint {thread_id:$tid, checkpoint_ns:$ns}) "
                    "RETURN n ORDER BY n.checkpoint_id DESC LIMIT 1", tid=tid, ns=ns,
                ).single()
            if rec is None:
                return None
            n = rec["n"]
            cid = n["checkpoint_id"]
            writes = s.run(
                "MATCH (w:AgentCheckpointWrite {thread_id:$tid, checkpoint_ns:$ns, checkpoint_id:$cid}) "
                "RETURN w ORDER BY w.task_id, w.idx", tid=tid, ns=ns, cid=cid,
            ).data()
        checkpoint = self.serde.loads_typed((n["type"], _unb64(n["checkpoint_blob"])))
        metadata = self.serde.loads_typed((n["metadata_type"], _unb64(n["metadata_blob"])))
        pending = [
            (w["w"]["task_id"], w["w"]["channel"],
             self.serde.loads_typed((w["w"]["type"], _unb64(w["w"]["blob"]))))
            for w in writes
        ]
        parent = n.get("parent_checkpoint_id")
        return CheckpointTuple(
            config={"configurable": {"thread_id": tid, "checkpoint_ns": ns, "checkpoint_id": cid}},
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=(
                {"configurable": {"thread_id": tid, "checkpoint_ns": ns, "checkpoint_id": parent}}
                if parent else None
            ),
            pending_writes=pending,
        )

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        tid = config["configurable"]["thread_id"] if config else None
        ns = config["configurable"].get("checkpoint_ns", "") if config else None
        before_id = get_checkpoint_id(before) if before else None
        where = ["n.thread_id = $tid"] if tid is not None else []
        if ns is not None:
            where.append("n.checkpoint_ns = $ns")
        if before_id:
            where.append("n.checkpoint_id < $before_id")
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        q = (f"MATCH (n:AgentCheckpoint) {clause} "
             "RETURN n.thread_id AS tid, n.checkpoint_ns AS ns, n.checkpoint_id AS cid "
             "ORDER BY n.checkpoint_id DESC")
        if limit:
            q += f" LIMIT {int(limit)}"
        with db.driver().session(database=_cfg.NEO4J_DATABASE) as s:
            keys = s.run(q, tid=tid, ns=ns, before_id=before_id).data()
        for k in keys:
            tup = self.get_tuple(
                {"configurable": {"thread_id": k["tid"], "checkpoint_ns": k["ns"],
                                  "checkpoint_id": k["cid"]}}
            )
            if tup is None:
                continue
            # metadata filter (post-fetch): blobs are serialised, so match in Python
            # rather than silently ignoring the arg. All items must match.
            if filter and not all(tup.metadata.get(fk) == fv for fk, fv in filter.items()):
                continue
            yield tup

    # ── async API (delegate to sync in a worker thread; sync neo4j driver is
    #     safe there and keeps a single code path for the spike) ───────────────
    async def aput(self, config, checkpoint, metadata, new_versions) -> RunnableConfig:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path="") -> None:
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def aget_tuple(self, config) -> CheckpointTuple | None:
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(self, config, *, filter=None, before=None, limit=None) -> AsyncIterator[CheckpointTuple]:
        tuples = await asyncio.to_thread(
            lambda: list(self.list(config, filter=filter, before=before, limit=limit))
        )
        for t in tuples:
            yield t
