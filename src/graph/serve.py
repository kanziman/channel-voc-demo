"""Local live-search endpoint for the dashboard playground (stdlib only).

Powers real-time hybrid search: a query typed in out/dashboard.html is embedded
here by the SAME fastembed model that built the graph (so query and document
vectors are consistent), then scored against Neo4j's vector + full-text indexes
and fused with RRF. No new dependencies — just http.server.

    python -m src.graph.serve            # → http://127.0.0.1:8756

The dashboard fetches this when present and falls back to precomputed sample
queries when it is not (so the static file always works on its own).
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config
from .retriever import hybrid_search


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # CORS preflight
        self._send(204, {})

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, {"ok": True, "model": config.EMBED_MODEL, "dim": config.EMBED_DIM})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/search"):
            self._send(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            query = (req.get("query") or "").strip()
            k = int(req.get("k", 6))
            if not query:
                self._send(400, {"error": "empty query"})
                return
            self._send(200, hybrid_search(query, k=k))
        except Exception as e:  # never 500 the demo silently
            self._send(500, {"error": str(e)})

    def log_message(self, *_):  # quiet
        pass


def main() -> int:
    addr = ("127.0.0.1", config.SEARCH_PORT)
    srv = ThreadingHTTPServer(addr, Handler)
    print(f"▶ VOC live hybrid search on http://{addr[0]}:{addr[1]}")
    print(f"  model={config.EMBED_MODEL} ({config.EMBED_DIM}d) · dense+fulltext+graph → RRF")
    print("  open out/dashboard.html and use the search playground.  Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
