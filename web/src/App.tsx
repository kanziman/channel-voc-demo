import { Boxes } from "lucide-react";
import { useState } from "react";
import "./App.css";

import { ChatStream } from "./components/ChatStream";
import { EvidencePanel } from "./components/EvidencePanel";
import type { EvidenceSubgraphRef } from "./components/EvidencePanel";
import { ApprovalCard } from "./components/ApprovalCard";
import { OntologyGraphTab } from "./console/OntologyGraphTab";
import { HybridSearchTab } from "./console/HybridSearchTab";
import { RootCauseGateTab } from "./console/RootCauseGateTab";

import type { ChatRequest, ChatResponse } from "./api/chat";
import type { SubgraphQuery, SubgraphResponse } from "./api/graph";
import type {
  DispatchRequest,
  DispatchResponse,
  InterruptPayload,
  RootCause,
  RunResponse,
} from "./api/agent";
import type { HybridSearchRequest, HybridSearchResponse } from "./api/search";

// The App shell (#44) wires the independently-built Phase 3 pieces together:
// the copilot view mounts the chat stream + evidence subgraph + approval gate,
// and "⤢ 탐색" crosses over to the 3-tab evidence console. Tokens only (§5-7).

export type View = "copilot" | "console";
export type ConsoleTab = "ontology" | "search" | "gate";

// Injection seams — default to the real API clients; tests pass fakes.
export interface AppDeps {
  postChatFn?: (req: ChatRequest) => Promise<ChatResponse>;
  getSubgraphFn?: (q?: SubgraphQuery) => Promise<SubgraphResponse>;
  dispatchFn?: (req: DispatchRequest) => Promise<DispatchResponse>;
  rootcausesFn?: () => Promise<{ rootcauses: RootCause[] }>;
  runFn?: (live?: boolean) => Promise<RunResponse>;
  searchFn?: (req: HybridSearchRequest) => Promise<HybridSearchResponse>;
}

export interface AppProps {
  deps?: AppDeps;
  initialThreadId?: string;
  initialView?: View;
  initialTab?: ConsoleTab;
  armStepMs?: number; // trace-sweep speed passthrough to ChatStream (tests use 0)
}

// Session thread id — owned by the shell, sent with every chat request and shared
// with the approval card so a LangGraph interrupt resumes on the same thread.
export function newThreadId(): string {
  return `t_${Math.random().toString(36).slice(2, 10)}`;
}

const CONSOLE_TABS: { key: ConsoleTab; label: string }[] = [
  { key: "ontology", label: "온톨로지 그래프" },
  { key: "search", label: "하이브리드 서치" },
  { key: "gate", label: "루트원인 승인" },
];

export function App({
  deps = {},
  initialThreadId,
  initialView = "copilot",
  initialTab = "ontology",
  armStepMs,
}: AppProps = {}) {
  const [threadId] = useState(() => initialThreadId ?? newThreadId());
  const [view, setView] = useState<View>(initialView);
  const [tab, setTab] = useState<ConsoleTab>(initialTab);
  const [latest, setLatest] = useState<ChatResponse | null>(null);

  const subgraphRef = (latest?.subgraph_ref ?? null) as EvidenceSubgraphRef | null;
  const interruptPayload = (latest?.interrupt_payload ?? null) as InterruptPayload | null;

  return (
    <div className="app">
      <header className="top">
        <div className="brandmark">
          <Boxes size={17} strokeWidth={2.4} />
        </div>
        <div className="top-title">
          <b>VOC Copilot</b> <span className="sub mono">· 채널톡 데스크 인라인</span>
        </div>
        <span className="badge mono">{threadId}</span>
      </header>

      {view === "copilot" ? (
        <div className="body">
          <ChatStream
            postChatFn={deps.postChatFn}
            threadId={threadId}
            armStepMs={armStepMs}
            onResponse={setLatest}
          />
          <div className="rail">
            <ApprovalCard
              interruptPayload={interruptPayload}
              threadId={threadId}
              dispatchFn={deps.dispatchFn}
            />
            <EvidencePanel
              subgraphRef={subgraphRef}
              onExplore={() => setView("console")}
              getSubgraphFn={deps.getSubgraphFn}
            />
          </div>
        </div>
      ) : (
        <div className="console-view" data-testid="console-view">
          <nav className="tabnav" role="tablist">
            <button type="button" className="tab-back" onClick={() => setView("copilot")}>
              ← 코파일럿
            </button>
            {CONSOLE_TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                role="tab"
                className="tab"
                data-tab={t.key}
                aria-selected={tab === t.key}
                onClick={() => setTab(t.key)}
              >
                {t.label}
              </button>
            ))}
          </nav>

          {tab === "ontology" && <OntologyGraphTab getSubgraphFn={deps.getSubgraphFn} />}
          {tab === "search" && <HybridSearchTab searchFn={deps.searchFn} />}
          {tab === "gate" && (
            <RootCauseGateTab
              rootcausesFn={deps.rootcausesFn}
              runFn={deps.runFn}
              dispatchFn={deps.dispatchFn}
            />
          )}
        </div>
      )}
    </div>
  );
}
