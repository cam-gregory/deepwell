import { useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";
import Markdown from "../components/Markdown";
import { ArrowUpIcon } from "../components/Icons";
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
    <div className="group flex items-center gap-2 rounded-2xl border border-line bg-surface p-2 shadow-card transition-shadow duration-300 focus-within:border-accent/50 focus-within:shadow-lift">
      <input
        className="flex-1 bg-transparent px-3 py-2.5 text-lg text-ink outline-none placeholder:text-ink-faint"
        type="text"
        placeholder={hasConversation ? "Reply or ask a follow-up…" : "Ask a question…"}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && send()}
      />
      <button
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent text-surface transition-all duration-200 ease-spring hover:bg-accent-deep active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
        onClick={send}
        disabled={loading || !input.trim()}
        aria-label="Send question"
      >
        <ArrowUpIcon size={20} />
      </button>
    </div>
  );

  return (
    <div className="mx-auto max-w-[1600px] px-6 pb-16 pt-8">
      <Nav />

      {!hasConversation ? (
        <div className="mx-auto w-full max-w-2xl pt-12 sm:pt-20">
          <p className="text-center text-xs font-medium uppercase tracking-[0.24em] text-accent-ink">
            Grounded answers, offline
          </p>
          <h1 className="mt-4 text-balance text-center font-display text-4xl font-semibold leading-[1.05] tracking-[-0.02em] text-ink sm:text-5xl">
            What would you like to know?
          </h1>
          <p className="mx-auto mt-4 max-w-md text-center text-ink-soft">
            Ask anything across the library. Every answer cites the documents it drew from.
          </p>
          <div className="mt-9">{inputRow}</div>
          {error && (
            <div className="mt-6 rounded-xl border border-data-clay/30 bg-data-clay/10 px-4 py-3 text-sm text-data-clay">
              {error}
            </div>
          )}
        </div>
      ) : (
        <div className="mx-auto w-full max-w-3xl">
          <div className="mb-4 flex justify-end">
            <button
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-ink-soft transition-colors hover:bg-ink/[0.06] hover:text-ink"
              onClick={newChat}
            >
              New chat
            </button>
          </div>

          <div className="space-y-5">
            {messages.map((turn, i) =>
              turn.role === "user" ? (
                <div key={i} className="flex justify-end animate-fade-up">
                  <div className="max-w-[85%] rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-surface">
                    {turn.content}
                  </div>
                </div>
              ) : (
                <div
                  key={i}
                  className="animate-fade-up rounded-2xl rounded-bl-md border border-line bg-surface px-6 py-5 shadow-card"
                >
                  {turn.content ? (
                    <Markdown text={turn.content} />
                  ) : (
                    <div className="space-y-2.5" aria-label="Searching knowledge base">
                      <div className="flex items-center gap-2 text-sm text-ink-faint">
                        <span className="h-2 w-2 animate-pulse-soft rounded-full bg-accent" />
                        Searching the library…
                      </div>
                      <div className="skeleton h-3.5 w-[92%] rounded" />
                      <div className="skeleton h-3.5 w-[78%] rounded" />
                      <div className="skeleton h-3.5 w-[85%] rounded" />
                    </div>
                  )}

                  {turn.sources && turn.sources.length > 0 && (
                    <div className="mt-6 border-t border-line pt-4">
                      <div className="mb-2.5 text-xs font-semibold uppercase tracking-[0.14em] text-ink-faint">
                        Sources
                      </div>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {turn.sources.map((s) => (
                          <div
                            key={s.id}
                            className="flex items-start gap-2.5 rounded-xl bg-surface-sunk px-3 py-2.5 text-sm"
                          >
                            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-accent-soft text-[11px] font-semibold text-accent-ink nums">
                              {s.id}
                            </span>
                            <div className="min-w-0">
                              <div className="truncate font-medium text-ink" title={s.source_file}>
                                {s.source_file}
                              </div>
                              <div className="text-xs text-ink-faint nums">
                                pages {s.page_start}–{s.page_end}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {turn.timings && (
                    <div className="mt-4 border-t border-line pt-3 text-xs text-ink-faint nums">
                      Retrieval {turn.timings.retrieval}s · First token {fmtTtft(turn.timings)} ·
                      Generation {turn.timings.generation}s · Total {turn.timings.total}s
                    </div>
                  )}
                </div>
              ),
            )}
          </div>

          {error && (
            <div className="mt-4 rounded-xl border border-data-clay/30 bg-data-clay/10 px-4 py-3 text-sm text-data-clay">
              {error}
            </div>
          )}

          <div ref={bottomRef} />

          <div className="sticky bottom-0 mt-4 bg-gradient-to-t from-paper via-paper/95 to-transparent pb-4 pt-3">
            {inputRow}
          </div>
        </div>
      )}
    </div>
  );
}
