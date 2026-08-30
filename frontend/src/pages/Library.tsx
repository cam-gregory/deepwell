import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Nav from "../components/Nav";
import { fetchLibraryPage, type LibraryDoc } from "../api";

const PAGE = 200;

function fmtSize(b: number | null): string {
  if (b == null) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}

const TYPE_META: Record<string, { icon: string; label: string; pill: string }> = {
  zim: { icon: "📘", label: "article", pill: "bg-violet-100 text-violet-800" },
  web: { icon: "🌐", label: "web", pill: "bg-emerald-100 text-emerald-800" },
  pdf: { icon: "📄", label: "PDF", pill: "bg-sky-100 text-sky-800" },
};

const DocCard = memo(function DocCard({
  doc,
  onClick,
  compact = false,
  selected = false,
}: {
  doc: LibraryDoc;
  onClick: () => void;
  compact?: boolean;
  selected?: boolean;
}) {
  const meta = TYPE_META[doc.type] ?? TYPE_META.pdf;
  const pages = doc.page_count ? `${doc.page_count} pages · ` : "";
  const size = doc.size_bytes ? fmtSize(doc.size_bytes) : "";
  const metaBits = [pages + size, doc.source].filter(Boolean).join(" · ");
  const descriptionText = doc.description ? doc.description.trim() : "";

  return (
    <div
      className={[
        "mb-2.5 flex items-center justify-between rounded-xl border bg-white px-5 py-4 transition cursor-pointer",
        selected ? "border-slate-300 shadow-sm ring-1 ring-slate-200/80" : "border-slate-100 hover:shadow-md hover:-translate-y-px",
        compact ? "min-h-[96px]" : "min-h-[122px]",
      ].join(" ")}
      onClick={onClick}
    >
      <div className="flex min-w-0 items-start">
        <span className="mr-3.5 text-2xl">{meta.icon}</span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold">{doc.title}</div>
          {descriptionText && (
            <div
              className={[
                "mt-1 max-w-[620px] text-slate-700 text-sm",
                compact ? "line-clamp-2" : "line-clamp-3",
              ].join(" ")}
            >
              {descriptionText}
            </div>
          )}
          <div className="mt-1 text-xs text-slate-500">{metaBits}</div>
        </div>
      </div>
      <span
        className={`ml-4 shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${meta.pill}`}
      >
        {meta.label}
      </span>
    </div>
  );
});

type DocFilter = "all" | "pdf" | "zim" | "web";

export default function Library() {
  const [query, setQuery] = useState("");
  const [docs, setDocs] = useState<LibraryDoc[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<LibraryDoc | null>(null);
  const [activeType, setActiveType] = useState<DocFilter>("all");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (q: string, reset: boolean, currentOffset: number) => {
    try {
      const data = await fetchLibraryPage(q, PAGE, reset ? 0 : currentOffset);
      setTotal(data.count);
      setDocs((prev) => (reset ? data.documents : [...prev, ...data.documents]));
      setOffset((reset ? 0 : currentOffset) + data.returned);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    load("", true, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const visibleDocs = useMemo(
    () => (activeType === "all" ? docs : docs.filter((doc) => doc.type === activeType)),
    [docs, activeType],
  );

  function handleFilterChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => load(value.trim(), true, 0), 250);
  }

  const hasDetailPanel = selectedDoc !== null;

  return (
    <div className="mx-auto max-w-[1600px] px-6 pb-16 pt-8">
      <Nav />

      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <div className="text-slate-500">Browse and open the documents and articles in Deepwell</div>
        </div>
        {hasDetailPanel && (
          <button
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            onClick={() => setSelectedDoc(null)}
          >
            Close detail
          </button>
        )}
      </div>

      <div className={hasDetailPanel ? "grid h-[calc(100vh-210px)] gap-6 xl:grid-cols-[minmax(280px,0.9fr)_minmax(0,2.1fr)]" : ""}>
        <div className={hasDetailPanel ? "min-w-0 overflow-hidden" : "mx-auto w-full max-w-3xl"}>
          <input
            className="mb-4 w-full box-border rounded-xl border border-slate-300 bg-white p-3.5 text-base"
            type="text"
            placeholder="Filter by title or description..."
            value={query}
            onChange={(e) => handleFilterChange(e.target.value)}
          />

          <div className="mb-4 flex flex-wrap gap-2">
            {[
              { value: "all", label: "All" },
              { value: "pdf", label: "PDF" },
              { value: "zim", label: "Articles" },
              { value: "web", label: "Web" },
            ].map((option) => (
              <button
                key={option.value}
                className={[
                  "rounded-full border px-3 py-1.5 text-sm transition",
                  activeType === option.value
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50",
                ].join(" ")}
                onClick={() => setActiveType(option.value as DocFilter)}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>

          {error && <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">{error}</div>}
          {!error && visibleDocs.length === 0 && (
            <div className="mt-6 text-slate-500">No documents found.</div>
          )}

          {!error && visibleDocs.length > 0 && (
            <div className="mb-3 text-[13px] text-slate-500">
              Showing {visibleDocs.length} of {total}
            </div>
          )}

          <div className={hasDetailPanel ? "h-[calc(100%-128px)] overflow-y-auto pr-1" : ""}>
            {visibleDocs.map((doc) => (
              <DocCard
                key={`${doc.source}-${doc.title}-${doc.open_url}`}
                doc={doc}
                compact={selectedDoc?.open_url === doc.open_url}
                selected={selectedDoc?.open_url === doc.open_url}
                onClick={() => setSelectedDoc(doc)}
              />
            ))}
          </div>

          {!error && offset < total && activeType === "all" && (
            <div className="mt-4 text-center">
              <button
                className="cursor-pointer rounded-lg border border-slate-300 bg-white px-5 py-2.5 hover:bg-slate-50"
                onClick={() => load(query.trim(), false, offset)}
              >
                Load more
              </button>
            </div>
          )}
        </div>

        {hasDetailPanel && selectedDoc && (
          <aside className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl ring-1 ring-slate-200/80">
            <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-slate-900">{selectedDoc.title}</div>
                <div className="truncate text-[11px] uppercase tracking-[0.14em] text-slate-500">
                  {selectedDoc.type}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-100"
                  onClick={() => setSelectedDoc(null)}
                >
                  Back to library
                </button>
                <a
                  href={selectedDoc.open_url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-white no-underline hover:bg-slate-800"
                >
                  Open in new tab
                </a>
              </div>
            </div>
            <iframe
              title={selectedDoc.title}
              src={selectedDoc.open_url}
              className="h-[calc(100%-57px)] w-full border-0 bg-white"
            />
          </aside>
        )}
      </div>
    </div>
  );
}
