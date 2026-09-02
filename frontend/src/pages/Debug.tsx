import { useState } from "react";
import Nav from "../components/Nav";
import { SearchIcon } from "../components/Icons";
import { fetchDebugSearch } from "../api";

export default function Debug() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(5);
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function run() {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError("");
    try {
      setResult(await fetchDebugSearch(q, limit));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1600px] px-6 pb-16 pt-8">
      <Nav />

      <div className="mb-7">
        <div className="mb-1.5 flex items-center gap-2.5">
          <h1 className="font-display text-3xl font-semibold tracking-[-0.02em] text-ink">Search inspector</h1>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-data-gold/12 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-data-gold">
            <span className="h-1.5 w-1.5 rounded-full bg-data-gold" />
            Admin tool
          </span>
        </div>
        <p className="text-ink-soft">Inspect dense rank, FTS rank, and rerank score per candidate.</p>
      </div>

      <div className="mb-6 flex gap-2 rounded-2xl border border-line bg-surface p-2 shadow-card">
        <div className="flex flex-1 items-center gap-2 pl-2 text-ink-faint">
          <SearchIcon size={18} />
          <input
            className="flex-1 bg-transparent py-2 text-base text-ink outline-none placeholder:text-ink-faint"
            type="text"
            placeholder="Query to inspect…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
          />
        </div>
        <input
          className="w-16 rounded-xl border border-line bg-surface-sunk px-3 py-2 text-center text-base text-ink outline-none nums focus:border-accent/50"
          type="number"
          min={1}
          max={20}
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          aria-label="Result limit"
        />
        <button
          className="rounded-xl bg-accent px-6 text-base font-medium text-surface transition-all duration-200 ease-spring hover:bg-accent-deep active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
          onClick={run}
          disabled={loading}
        >
          {loading ? "Running…" : "Run"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-data-clay/30 bg-data-clay/10 px-4 py-3 text-sm text-data-clay">
          {error}
        </div>
      )}

      {result !== null && (
        <pre className="overflow-auto rounded-2xl border border-line bg-surface p-4 font-mono text-xs text-ink-soft shadow-card">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}
