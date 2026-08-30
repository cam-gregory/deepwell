import { useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";
import Markdown from "../components/Markdown";
import { streamAsk, type ChatMessage, type Source, type Timings } from "../api";

interface Turn {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  timings?: Timings | null;
}

function fmtTtft(t: Timings): string {
  return t.time_to_first_token == null ? "–" : `${t.time_to_first_token}s`;
}

export default function Ask() {
  const [messages, setMessages] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const hasConversation = messages.length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  function updateLastAssistant(apply: (turn: Turn) => Turn) {
    setMessages((prev) => {
      const copy = prev.slice();
      const i = copy.length - 1;
      if (i < 0 || copy[i].role !== "assistant") return prev;
      copy[i] = apply(copy[i]);
      return copy;
    });
  }

  async function send() {
    const q = input.trim();
    if (!q || loading) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const history: Turn[] = [...messages, { role: "user", content: q }];
    setMessages([...history, { role: "assistant", content: "" }]);
    setInput("");
    setLoading(true);
    setError("");

    const outgoing: ChatMessage[] = history.map(({ role, content }) => ({ role, content }));

    try {
      await streamAsk(
        outgoing,
        (event) => {
          if (event.type === "sources") {
            updateLastAssistant((t) => ({ ...t, sources: event.sources }));
          } else if (event.type === "token") {
            updateLastAssistant((t) => ({ ...t, content: t.content + event.text }));
            setLoading(false);
          } else if (event.type === "timings") {
            updateLastAssistant((t) => ({ ...t, timings: event.timings }));
          } else if (event.type === "error") {
            setError(event.message);
          }
        },
        controller.signal,
      );
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setLoading(false);
    }
  }

  function newChat() {
    abortRef.current?.abort();
    setMessages([]);
    setInput("");
    setError("");
    setLoading(false);
  }

  const inputRow = (
    <div className="flex gap-3">
      <input
        className="flex-1 text-lg p-4 border border-slate-300 rounded-xl"
        type="text"
        placeholder={hasConversation ? "Reply or ask a follow-up..." : "Ask a question..."}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && send()}
      />
      <button
        className="rounded-xl bg-slate-900 px-6 text-base font-medium text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        onClick={send}
        disabled={loading}
      >
        Send
      </button>
    </div>
  );

  return (
    <div className="mx-auto max-w-[1600px] px-6 pb-16 pt-8">
      <Nav />

      {!hasConversation ? (
        <div className="mx-auto w-full max-w-3xl pt-10 sm:pt-16">
          <h1 className="text-center text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            What would you like to know?
          </h1>
          <div className="mt-8">{inputRow}</div>
          {error && (
            <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">
              {error}
            </div>
          )}
        </div>
      ) : (
        <div className="mx-auto w-full max-w-3xl">
          <div className="mb-4 flex justify-end">
            <button
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 transition hover:bg-slate-50"
              onClick={newChat}
            >
              New chat
            </button>
          </div>

          <div className="space-y-4">
            {messages.map((turn, i) =>
              turn.role === "user" ? (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl bg-slate-900 px-4 py-2.5 text-white">
                    {turn.content}
                  </div>
                </div>
              ) : (
                <div key={i} className="rounded-2xl bg-white px-6 py-5 shadow-sm ring-1 ring-slate-200/70">
                  {turn.content ? (
                    <Markdown text={turn.content} />
                  ) : (
                    <div className="text-slate-500">Searching knowledge base...</div>
                  )}

                  {turn.sources && turn.sources.length > 0 && (
                    <div className="mt-6 pt-4 border-t border-slate-100">
                      <strong>Sources</strong>
                      {turn.sources.map((s) => (
                        <div key={s.id} className="bg-slate-100 p-3 mt-2 rounded-lg text-sm">
                          [Source {s.id}] {s.source_file} — pages {s.page_start}-{s.page_end}
                        </div>
                      ))}
                    </div>
                  )}

                  {turn.timings && (
                    <div className="mt-4 pt-3 border-t border-slate-100 text-slate-500 text-xs">
                      Retrieval {turn.timings.retrieval}s · First token {fmtTtft(turn.timings)} ·
                      Generation {turn.timings.generation}s · Total {turn.timings.total}s
                    </div>
                  )}
                </div>
              ),
            )}
          </div>

          {error && (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">
              {error}
            </div>
          )}

          <div ref={bottomRef} />

          <div className="sticky bottom-0 mt-4 bg-slate-100/95 py-4 backdrop-blur-sm">
            {inputRow}
          </div>
        </div>
      )}
    </div>
  );
}
