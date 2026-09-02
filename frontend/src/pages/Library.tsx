import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Nav from "../components/Nav";
import { docIconFor, ExternalIcon } from "../components/Icons";
import { fetchLibraryPage, fetchCategories, type LibraryDoc, type CategoryNode } from "../api";

const PAGE = 200;

function fmtSize(b: number | null): string {
  if (b == null) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}

const TYPE_META: Record<string, { label: string; pill: string; tint: string }> = {
  zim: { label: "article", pill: "bg-data-plum/12 text-data-plum", tint: "bg-data-plum/12 text-data-plum" },
  web: { label: "web", pill: "bg-data-moss/12 text-data-moss", tint: "bg-data-moss/12 text-data-moss" },
  pdf: { label: "PDF", pill: "bg-data-slate/12 text-data-slate", tint: "bg-data-slate/12 text-data-slate" },
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
  const Icon = docIconFor(doc.type);
  const pages = doc.page_count ? `${doc.page_count} pages · ` : "";
  const size = doc.size_bytes ? fmtSize(doc.size_bytes) : "";
  const metaBits = [pages + size, doc.source].filter(Boolean).join(" · ");
  const descriptionText = doc.description ? doc.description.trim() : "";

  return (
    <div
      role="button"
      tabIndex={0}
      className={[
        "group mb-2.5 flex cursor-pointer items-center justify-between rounded-2xl border bg-surface px-5 py-4 transition-all duration-200 ease-spring",
        selected
          ? "border-accent/40 shadow-lift ring-1 ring-accent/20"
          : "border-line hover:-translate-y-0.5 hover:border-line-strong hover:shadow-card",
        compact ? "min-h-[92px]" : "min-h-[118px]",
      ].join(" ")}
      onClick={onClick}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onClick())}
    >
      <div className="flex min-w-0 items-start">
        <span className={`mr-4 mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${meta.tint}`}>
          <Icon size={19} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-ink">{doc.title}</div>
          {descriptionText && (
            <div
              className={[
                "mt-1 max-w-[620px] text-sm text-ink-soft",
                compact ? "line-clamp-2" : "line-clamp-3",
              ].join(" ")}
            >
              {descriptionText}
            </div>
          )}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-faint nums">
            {metaBits}
            {doc.subcategory && (
              <span className="rounded-md bg-surface-sunk px-2 py-0.5 font-medium text-ink-soft">
                {doc.subcategory}
              </span>
            )}
          </div>
        </div>
      </div>
      <span
        className={`ml-4 shrink-0 whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-semibold ${meta.pill}`}
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
  const [categoryTree, setCategoryTree] = useState<CategoryNode[]>([]);
  const [activeCategory, setActiveCategory] = useState("");
  const [activeSub, setActiveSub] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(
    async (q: string, reset: boolean, currentOffset: number, category: string, sub: string) => {
      try {
        const data = await fetchLibraryPage(q, PAGE, reset ? 0 : currentOffset, category, sub);
        setTotal(data.count);
        setDocs((prev) => (reset ? data.documents : [...prev, ...data.documents]));
        setOffset((reset ? 0 : currentOffset) + data.returned);
        setError("");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [],
  );

  useEffect(() => {
    load("", true, 0, "", "");
    fetchCategories()
      .then(setCategoryTree)
      .catch(() => setCategoryTree([]));
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

  const subcategories = useMemo(
    () => categoryTree.find((c) => c.category === activeCategory)?.subcategories ?? [],
    [categoryTree, activeCategory],
  );

  function handleFilterChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => load(value.trim(), true, 0, activeCategory, activeSub), 250);
  }

  function handleCategoryChange(value: string) {
    setActiveCategory(value);
    setActiveSub("");
    load(query.trim(), true, 0, value, "");
  }

  function handleSubChange(value: string) {
    setActiveSub(value);
    load(query.trim(), true, 0, activeCategory, value);
  }

  const hasDetailPanel = selectedDoc !== null;

  return (
    <div className="mx-auto max-w-[1600px] px-6 pb-16 pt-8">
      <Nav />

      <div className="mb-7 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-[-0.02em] text-ink">Library</h1>
          <p className="mt-1.5 text-ink-soft">Browse and open every document and article in Deepwell.</p>
        </div>
        {hasDetailPanel && (
          <button
            className="rounded-lg border border-line bg-surface px-3 py-2 text-sm font-medium text-ink-soft transition-colors hover:border-line-strong hover:text-ink"
            onClick={() => setSelectedDoc(null)}
          >
            Close detail
          </button>
        )}
      </div>

      <div className={hasDetailPanel ? "grid h-[calc(100vh-230px)] gap-6 xl:grid-cols-[minmax(280px,0.9fr)_minmax(0,2.1fr)]" : ""}>
        <div className={hasDetailPanel ? "min-w-0 overflow-hidden" : "mx-auto w-full max-w-3xl"}>
          <div className="relative mb-4">
            <input
              className="w-full box-border rounded-xl border border-line bg-surface py-3.5 pl-4 pr-4 text-base text-ink shadow-inset outline-none transition-colors placeholder:text-ink-faint focus:border-accent/50"
              type="text"
              placeholder="Filter by title or description…"
              value={query}
              onChange={(e) => handleFilterChange(e.target.value)}
            />
          </div>

          <div className="mb-5 flex flex-wrap items-center gap-2">
            {[
              { value: "all", label: "All" },
              { value: "pdf", label: "PDF" },
              { value: "zim", label: "Articles" },
              { value: "web", label: "Web" },
            ].map((option) => (
              <button
                key={option.value}
                className={[
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  activeType === option.value
                    ? "bg-ink text-surface"
                    : "text-ink-soft hover:bg-ink/[0.06] hover:text-ink",
                ].join(" ")}
                onClick={() => setActiveType(option.value as DocFilter)}
                type="button"
              >
                {option.label}
              </button>
            ))}

            <div className="ml-auto flex flex-wrap items-center gap-2">
              <select
                className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm text-ink-soft transition-colors hover:border-line-strong"
                value={activeCategory}
                onChange={(e) => handleCategoryChange(e.target.value)}
              >
                <option value="">All categories</option>
                {categoryTree.map((c) => (
                  <option key={c.category} value={c.category}>
                    {c.category} ({c.documents.toLocaleString()})
                  </option>
                ))}
              </select>
              {subcategories.length > 0 && (
                <select
                  className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm text-ink-soft transition-colors hover:border-line-strong"
                  value={activeSub}
                  onChange={(e) => handleSubChange(e.target.value)}
                >
                  <option value="">All subcategories</option>
                  {subcategories.map((s) => (
                    <option key={s.subcategory} value={s.subcategory}>
                      {s.subcategory} ({s.documents.toLocaleString()})
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {error && (
            <div className="mt-6 rounded-xl border border-data-clay/30 bg-data-clay/10 px-4 py-3 text-sm text-data-clay">
              {error}
            </div>
          )}
          {!error && visibleDocs.length === 0 && (
            <div className="mt-10 rounded-2xl border border-dashed border-line-strong bg-surface/50 px-6 py-12 text-center">
              <div className="font-display text-lg font-semibold text-ink">No documents match</div>
              <p className="mx-auto mt-1.5 max-w-sm text-sm text-ink-soft">
                Try a broader search term or clear the category filters to see the full library.
              </p>
            </div>
          )}

          {!error && visibleDocs.length > 0 && (
            <div className="mb-3 text-[13px] text-ink-faint nums">
              Showing {visibleDocs.length} of {total.toLocaleString()}
            </div>
          )}

          <div className={hasDetailPanel ? "h-[calc(100%-138px)] overflow-y-auto pr-1" : ""}>
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
            <div className="mt-5 text-center">
              <button
                className="cursor-pointer rounded-xl border border-line bg-surface px-5 py-2.5 text-sm font-medium text-ink-soft transition-colors hover:border-line-strong hover:text-ink"
                onClick={() => load(query.trim(), false, offset, activeCategory, activeSub)}
              >
                Load more
              </button>
            </div>
          )}
        </div>

        {hasDetailPanel && selectedDoc && (
          <aside className="overflow-hidden rounded-3xl border border-line bg-surface shadow-lift">
            <div className="flex items-center justify-between border-b border-line bg-surface-sunk px-4 py-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-ink">{selectedDoc.title}</div>
                <div className="truncate text-[11px] uppercase tracking-[0.16em] text-ink-faint">
                  {selectedDoc.type}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs font-medium text-ink-soft transition-colors hover:border-line-strong hover:text-ink"
                  onClick={() => setSelectedDoc(null)}
                >
                  Back to library
                </button>
                <a
                  href={selectedDoc.open_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-xs font-medium text-surface no-underline transition-colors hover:bg-accent-deep"
                >
                  <ExternalIcon size={14} />
                  Open
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
