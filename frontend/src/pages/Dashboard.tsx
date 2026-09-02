import { useEffect, useMemo, useState } from "react";
import Nav from "../components/Nav";
import { docIconFor } from "../components/Icons";
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

const SOURCE_META: Record<string, { label: string; bar: string; pill: string }> = {
  pdf: { label: "PDFs", bar: "bg-data-slate", pill: "bg-data-slate/12 text-data-slate" },
  zim: { label: "Articles (ZIM)", bar: "bg-data-plum", pill: "bg-data-plum/12 text-data-plum" },
  web: { label: "Web articles", bar: "bg-data-moss", pill: "bg-data-moss/12 text-data-moss" },
};

const CATEGORY_BARS = [
  "bg-data-teal",
  "bg-data-clay",
  "bg-data-gold",
  "bg-data-plum",
  "bg-data-slate",
  "bg-data-moss",
];

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface px-6 py-5 shadow-card">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">{label}</div>
      <div className="mt-2 font-display text-3xl font-semibold tracking-[-0.02em] text-ink nums">{value}</div>
      {sub && <div className="mt-1 text-sm text-ink-soft">{sub}</div>}
    </div>
  );
}

function Bar({ fraction, color }: { fraction: number; color: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-sunk">
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

      <div className="mb-7">
        <h1 className="font-display text-3xl font-semibold tracking-[-0.02em] text-ink">Dashboard</h1>
        <p className="mt-1.5 text-ink-soft">An overview of everything indexed in Deepwell.</p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-data-clay/30 bg-data-clay/10 px-4 py-3 text-sm text-data-clay">
          {error}
        </div>
      )}

      {!stats && !error && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="rounded-2xl border border-line bg-surface px-6 py-5 shadow-card">
                <div className="skeleton h-3 w-24 rounded" />
                <div className="skeleton mt-3 h-8 w-20 rounded" />
                <div className="skeleton mt-2 h-3 w-28 rounded" />
              </div>
            ))}
          </div>
        </div>
      )}

      {stats && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total size" value={fmtSize(stats.size.total_bytes)} sub="Sources, index & database" />
            <StatCard label="Documents" value={fmtNum(stats.documents)} sub={`${fmtNum(stats.pages)} pages`} />
            <StatCard label="Chunks" value={fmtNum(stats.chunks)} sub="Searchable passages" />
            <StatCard label="Source files" value={fmtSize(stats.size.sources_bytes)} sub="PDFs, ZIM & web snapshots" />
          </div>

          <div className="rounded-2xl border border-line bg-surface px-6 py-5 shadow-card">
            <div className="mb-4 text-sm font-semibold text-ink">Top-level categories</div>
            <div className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
              {stats.by_top_category.map((c, i) => (
                <div key={c.category}>
                  <div className="mb-1.5 flex items-center justify-between text-sm">
                    <span className="text-ink-soft">{c.category}</span>
                    <span className="text-xs font-semibold text-ink-faint nums">{fmtNum(c.documents)}</span>
                  </div>
                  <Bar fraction={c.documents / maxTopCat} color={CATEGORY_BARS[i % CATEGORY_BARS.length]} />
                </div>
              ))}
              {stats.by_top_category.length === 0 && (
                <div className="text-sm text-ink-faint">No categories yet — run the categorizer stage.</div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-line bg-surface px-6 py-5 shadow-card">
              <div className="mb-4 text-sm font-semibold text-ink">Documents by source type</div>
              <div className="space-y-4">
                {stats.by_source_type.map((s) => {
                  const meta = SOURCE_META[s.type] ?? {
                    label: s.type,
                    bar: "bg-data-slate",
                    pill: "bg-surface-sunk text-ink-soft",
                  };
                  const Icon = docIconFor(s.type);
                  return (
                    <div key={s.type}>
                      <div className="mb-1.5 flex items-center justify-between text-sm">
                        <span className="flex items-center gap-2 text-ink-soft">
                          <Icon size={16} />
                          {meta.label}
                        </span>
                        <span className={`rounded-md px-2 py-0.5 text-xs font-semibold nums ${meta.pill}`}>
                          {fmtNum(s.documents)}
                        </span>
                      </div>
                      <Bar fraction={s.documents / maxSource} color={meta.bar} />
                    </div>
                  );
                })}
                {stats.by_source_type.length === 0 && (
                  <div className="text-sm text-ink-faint">No documents yet.</div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-line bg-surface px-6 py-5 shadow-card">
              <div className="mb-4 text-sm font-semibold text-ink">Information types (by passage)</div>
              <div className="space-y-4">
                {stats.by_category.map((c, i) => (
                  <div key={c.category}>
                    <div className="mb-1.5 flex items-center justify-between text-sm">
                      <span className="text-ink-soft">{c.label}</span>
                      <span className="text-xs font-semibold text-ink-faint nums">{fmtNum(c.chunks)}</span>
                    </div>
                    <Bar fraction={c.chunks / maxCategory} color={CATEGORY_BARS[i % CATEGORY_BARS.length]} />
                  </div>
                ))}
                {stats.by_category.length === 0 && (
                  <div className="text-sm text-ink-faint">No categorized content yet.</div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-line bg-surface px-6 py-5 shadow-card">
            <div className="mb-4 text-sm font-semibold text-ink">Storage breakdown</div>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              {[
                { label: "PDFs", bytes: stats.size.pdf_bytes },
                { label: "ZIM archives", bytes: stats.size.zim_bytes },
                { label: "Web snapshots", bytes: stats.size.web_bytes },
                { label: "Vector index", bytes: stats.size.vector_bytes },
                { label: "Database", bytes: stats.size.database_bytes },
              ].map((item) => (
                <div key={item.label} className="rounded-xl bg-surface-sunk px-4 py-3">
                  <div className="text-xs font-medium text-ink-faint">{item.label}</div>
                  <div className="mt-1 text-lg font-semibold text-ink nums">{fmtSize(item.bytes)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
