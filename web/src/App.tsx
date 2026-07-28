import { Boxes } from "lucide-react";
import "./App.css";

// Scaffold shell for the VOC Copilot (PHASE3 §2). This is the token-driven
// skeleton the real components (chat stream, evidence subgraph, approval card,
// 3-tab console) will fill in. It exists to prove tokens.css loads end-to-end
// and that the layout frame is gradient-free and var(--token) only.

const ARMS = [
  { key: "D", label: "Dense", token: "--arm-dense" },
  { key: "S", label: "Sparse", token: "--arm-sparse" },
  { key: "G", label: "Graph", token: "--arm-graph" },
] as const;

export function App() {
  return (
    <div className="app">
      <header className="top">
        <div className="brandmark">
          <Boxes size={17} strokeWidth={2.4} />
        </div>
        <div className="top-title">
          <b>VOC Copilot</b> <span className="sub mono">· 채널톡 데스크 인라인</span>
        </div>
        <span className="badge mono">Phase 3 · Scaffold</span>
      </header>

      <div className="body">
        <section className="chat">
          <div className="stream">
            <div className="msg bot">
              <div className="av bot mono">VC</div>
              <div className="bubble">
                토큰 시스템이 로드된 스캐폴드입니다. 이 프레임 위에 대화 스트림 ·
                retrieval trace · 승인 카드가 올라갑니다.
                <div className="trace mono">
                  retrieval
                  {ARMS.map((a) => (
                    <span
                      key={a.key}
                      className="arm"
                      style={{ background: `var(${a.token})` }}
                      title={a.label}
                    >
                      {a.key}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="composer">
            <div className="box">
              <span className="mono prompt">›</span>
              <input placeholder="그래프에 질문하기…" disabled />
            </div>
          </div>
        </section>

        <aside className="evidence">
          <div className="ev-h mono">근거 서브그래프</div>
          <div className="ev-placeholder mono">
            GraphRAG 서브그래프가 여기 그려집니다
          </div>
          <div className="ev-legend mono">
            <span>
              <i style={{ background: "var(--node-rootcause)" }} />
              RootCause
            </span>
            <span>
              <i style={{ background: "var(--node-component)" }} />
              Component
            </span>
            <span>
              <i style={{ background: "var(--node-symptom)" }} />
              Symptom
            </span>
            <span>
              <i style={{ background: "var(--node-conversation)" }} />
              Conversation
            </span>
          </div>
        </aside>
      </div>
    </div>
  );
}
