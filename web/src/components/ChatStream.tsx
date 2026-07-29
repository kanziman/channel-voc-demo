// VOC Copilot chat stream (§2, §5-5). Operator asks → before the answer the
// D/S/G retrieval arms light in sequence (visualizing the 3-way hybrid search),
// then the answer is rendered verbatim from the server (real graph values, no
// client-side regeneration). Tokens only, no gradients (§5-7).
import { useState } from "react";
import { postChat } from "../api/chat";
import type { ChatRequest, ChatResponse } from "../api/chat";

export const ARM_ORDER = ["D", "S", "G"] as const;
type ArmKey = (typeof ARM_ORDER)[number];

// The three arms are a load-bearing visual language (§ DESIGN.md) — key,
// palette token, and the backend arm name they map to.
const ARM_META: Record<ArmKey, { label: string; token: string; backend: string }> = {
  D: { label: "Dense", token: "--arm-dense", backend: "dense" },
  S: { label: "Sparse", token: "--arm-sparse", backend: "sparse" },
  G: { label: "Graph", token: "--arm-graph", backend: "graph" },
};

type Role = "user" | "bot";
interface StreamMessage {
  id: string;
  role: Role;
  text: string;
  arms?: string[];
  gate?: ChatResponse["gate"];
  confidence?: number;
  error?: boolean;
}

export interface ChatStreamProps {
  postChatFn?: (req: ChatRequest) => Promise<ChatResponse>;
  armStepMs?: number;
}

let _seq = 0;
const uid = () => `m${++_seq}`;

// Arm chip fill: the arm's palette token when active (lit / hit), muted otherwise.
const armStyle = (key: ArmKey, active: boolean): React.CSSProperties => ({
  background: active ? `var(${ARM_META[key].token})` : "var(--surface-3)",
  color: active ? "var(--bg)" : "var(--dim)",
});

export function ChatStream({ postChatFn = postChat, armStepMs = 220 }: ChatStreamProps) {
  const [messages, setMessages] = useState<StreamMessage[]>([]);
  const [input, setInput] = useState("");
  const [litCount, setLitCount] = useState(0);
  const [tracing, setTracing] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || tracing) return;

    setInput("");
    setMessages((m) => [...m, { id: uid(), role: "user", text: q }]);
    setTracing(true);
    setLitCount(0);

    // Arm sweep: light D → S → G, one every armStepMs. Resolves when all lit.
    const armsDone = new Promise<void>((resolve) => {
      let n = 0;
      const tick = () => {
        n += 1;
        setLitCount(n);
        if (n >= ARM_ORDER.length) resolve();
        else setTimeout(tick, armStepMs);
      };
      setTimeout(tick, armStepMs);
    });

    // The answer appears only after BOTH the arms finish AND the response lands.
    Promise.all([postChatFn({ message: q }), armsDone])
      .then(([resp]) => {
        setMessages((m) => [
          ...m,
          {
            id: uid(),
            role: "bot",
            text: resp.answer,
            arms: resp.arms,
            gate: resp.gate,
            confidence: resp.confidence,
          },
        ]);
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : String(err);
        setMessages((m) => [
          ...m,
          { id: uid(), role: "bot", text: `오류: ${message}`, error: true },
        ]);
      })
      .finally(() => {
        setTracing(false);
        setLitCount(0);
      });
  }

  return (
    <section className="chat">
      <div className="stream">
        {messages.map((msg) => (
          <div key={msg.id} className={`msg ${msg.role}`} data-role={msg.role}>
            {msg.role === "bot" && <div className="av bot mono">VC</div>}
            <div className="bubble">
              <div className="answer">{msg.text}</div>
              {msg.role === "bot" && msg.arms !== undefined && !msg.error && (
                <div className="trace mono">
                  {ARM_ORDER.map((k) => {
                    const hit = msg.arms!.includes(ARM_META[k].backend);
                    return (
                      <span
                        key={k}
                        className="arm"
                        data-testid={`arm-hit-${k}`}
                        data-arm={k}
                        data-hit={hit ? "true" : "false"}
                        title={ARM_META[k].label}
                        style={armStyle(k, hit)}
                      >
                        {k}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ))}

        {tracing && (
          <div className="msg bot" data-role="trace">
            <div className="av bot mono">VC</div>
            <div className="bubble">
              <div className="trace mono">
                retrieval
                {ARM_ORDER.map((k, i) => {
                  const state = i < litCount ? "lit" : "pending";
                  return (
                    <span
                      key={k}
                      className="arm"
                      data-arm={k}
                      data-state={state}
                      title={ARM_META[k].label}
                      style={armStyle(k, state === "lit")}
                    >
                      {k}
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <div className="box">
          <span className="mono prompt">›</span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="그래프에 질문하기…"
          />
        </div>
      </form>
    </section>
  );
}
