import { useState } from "react";
import Nav from "../components/Nav";
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

      <div className="mb-6 text-slate-500">
        Inspect dense rank, FTS rank, and rerank score per candidate.
      </div>

      <div className="mb-6 flex gap-3">
        <input
          className="flex-1 text-base p-3.5 border border-slate-300 rounded-xl"
          type="text"
          placeholder="Query to inspect..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <input
          className="w-20 text-base p-3.5 border border-slate-300 rounded-xl"
          type="number"
          min={1}
          max={20}
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
        />
        <button
          className="rounded-xl bg-slate-900 px-6 text-base font-medium text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          onClick={run}
          disabled={loading}
        >
          Run
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">{error}</div>
      )}

      {result !== null && (
        <pre className="bg-white p-4 rounded-xl overflow-auto text-xs">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}
