import { useEffect, useMemo, useState } from "react";
import Nav from "../components/Nav";
import { fetchStats, type CorpusStats } from "../api";

function fmtSize(b: number): string {
  if (b <= 0) return "0 B";
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(0)} KB`;
  if (b < 1073741824) return `${(b / 1048576).toFixed(1)} MB`;
  return `${(b / 1073741824).toFixed(2)} GB`;
}

function fmtNum(n: number): string {
  return n.toLocaleString();
}

const SOURCE_META: Record<string, { icon: string; label: string; bar: string; pill: string }> = {
  pdf: { icon: "📄", label: "PDFs", bar: "bg-sky-500", pill: "bg-sky-100 text-sky-800" },
  zim: { icon: "📘", label: "Articles (ZIM)", bar: "bg-violet-500", pill: "bg-violet-100 text-violet-800" },
  web: { icon: "🌐", label: "Web articles", bar: "bg-emerald-500", pill: "bg-emerald-100 text-emerald-800" },
};

const CATEGORY_BARS = [
  "bg-amber-500",
  "bg-rose-500",
  "bg-indigo-500",
  "bg-teal-500",
  "bg-slate-400",
  "bg-fuchsia-500",
];

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white px-6 py-5 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">{value}</div>
      {sub && <div className="mt-1 text-sm text-slate-500">{sub}</div>}
    </div>
  );
}

function Bar({ fraction, color }: { fraction: number; color: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.max(fraction * 100, 2)}%` }} />
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const maxSource = useMemo(
    () => (stats ? Math.max(1, ...stats.by_source_type.map((s) => s.documents)) : 1),
    [stats],
  );
  const maxTopCat = useMemo(
    () => (stats ? Math.max(1, ...stats.by_top_category.map((c) => c.documents)) : 1),
    [stats],
  );
  const maxCategory = useMemo(
    () => (stats ? Math.max(1, ...stats.by_category.map((c) => c.chunks)) : 1),
    [stats],
  );

  return (
    <div className="mx-auto max-w-[1600px] px-6 pb-16 pt-8">
      <Nav />

      <div className="mb-6">
        <div className="text-slate-500">An overview of everything indexed in Deepwell</div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      {!stats && !error && <div className="text-sm text-slate-500">Loading…</div>}

      {stats && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total size" value={fmtSize(stats.size.total_bytes)} sub="Sources, index & database" />
            <StatCard label="Documents" value={fmtNum(stats.documents)} sub={`${fmtNum(stats.pages)} pages`} />
            <StatCard label="Chunks" value={fmtNum(stats.chunks)} sub="Searchable passages" />
            <StatCard label="Source files" value={fmtSize(stats.size.sources_bytes)} sub="PDFs, ZIM & web snapshots" />
          </div>

          <div className="rounded-2xl border border-slate-100 bg-white px-6 py-5 shadow-sm">
            <div className="mb-4 text-sm font-semibold text-slate-900">Top-level categories</div>
            <div className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
              {stats.by_top_category.map((c, i) => (
                <div key={c.category}>
                  <div className="mb-1.5 flex items-center justify-between text-sm">
                    <span className="text-slate-700">{c.category}</span>
                    <span className="text-xs font-semibold text-slate-500">{fmtNum(c.documents)}</span>
                  </div>
                  <Bar fraction={c.documents / maxTopCat} color={CATEGORY_BARS[i % CATEGORY_BARS.length]} />
                </div>
              ))}
              {stats.by_top_category.length === 0 && (
                <div className="text-sm text-slate-500">No categories yet — run the categorizer stage.</div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-100 bg-white px-6 py-5 shadow-sm">
              <div className="mb-4 text-sm font-semibold text-slate-900">Documents by source type</div>
              <div className="space-y-4">
                {stats.by_source_type.map((s) => {
                  const meta = SOURCE_META[s.type] ?? {
                    icon: "📁",
                    label: s.type,
                    bar: "bg-slate-400",
                    pill: "bg-slate-100 text-slate-700",
                  };
                  return (
                    <div key={s.type}>
                      <div className="mb-1.5 flex items-center justify-between text-sm">
                        <span className="flex items-center gap-2 text-slate-700">
                          <span>{meta.icon}</span>
                          {meta.label}
                        </span>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${meta.pill}`}>
                          {fmtNum(s.documents)}
                        </span>
                      </div>
                      <Bar fraction={s.documents / maxSource} color={meta.bar} />
                    </div>
                  );
                })}
                {stats.by_source_type.length === 0 && (
                  <div className="text-sm text-slate-500">No documents yet.</div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-white px-6 py-5 shadow-sm">
              <div className="mb-4 text-sm font-semibold text-slate-900">Information types (by passage)</div>
              <div className="space-y-4">
                {stats.by_category.map((c, i) => (
                  <div key={c.category}>
                    <div className="mb-1.5 flex items-center justify-between text-sm">
                      <span className="text-slate-700">{c.label}</span>
                      <span className="text-xs font-semibold text-slate-500">{fmtNum(c.chunks)}</span>
                    </div>
                    <Bar fraction={c.chunks / maxCategory} color={CATEGORY_BARS[i % CATEGORY_BARS.length]} />
                  </div>
                ))}
                {stats.by_category.length === 0 && (
                  <div className="text-sm text-slate-500">No categorized content yet.</div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-100 bg-white px-6 py-5 shadow-sm">
            <div className="mb-4 text-sm font-semibold text-slate-900">Storage breakdown</div>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              {[
                { label: "PDFs", bytes: stats.size.pdf_bytes },
                { label: "ZIM archives", bytes: stats.size.zim_bytes },
                { label: "Web snapshots", bytes: stats.size.web_bytes },
                { label: "Vector index", bytes: stats.size.vector_bytes },
                { label: "Database", bytes: stats.size.database_bytes },
              ].map((item) => (
                <div key={item.label} className="rounded-xl bg-slate-50 px-4 py-3">
                  <div className="text-xs font-medium text-slate-500">{item.label}</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{fmtSize(item.bytes)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
