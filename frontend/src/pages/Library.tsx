import { memo, useCallback, useEffect, useMemo, useState } from "react";
import Nav from "../components/Nav";
import {
  docIconFor,
  categoryMeta,
  SearchIcon,
  GridIcon,
  ListIcon,
  ArrowLeftIcon,
  ChevronRightIcon,
  ExternalIcon,
} from "../components/Icons";
import {
  fetchLibraryPage,
  fetchCategories,
  type LibraryDoc,
  type CategoryNode,
  type LibrarySort,
} from "../api";

const PAGE = 200;

const TYPE_META: Record<string, { label: string; pill: string; tint: string }> = {
  zim: { label: "article", pill: "bg-data-plum/12 text-data-plum", tint: "bg-data-plum/12 text-data-plum" },
  web: { label: "web", pill: "bg-data-moss/12 text-data-moss", tint: "bg-data-moss/12 text-data-moss" },
  pdf: { label: "PDF", pill: "bg-data-slate/12 text-data-slate", tint: "bg-data-slate/12 text-data-slate" },
};

type DocFilter = "all" | "pdf" | "zim" | "web";

const TYPE_OPTIONS: { value: DocFilter; label: string }[] = [
  { value: "all", label: "All types" },
  { value: "pdf", label: "PDF" },
  { value: "zim", label: "Articles" },
  { value: "web", label: "Web" },
];

const SORT_OPTIONS: { value: LibrarySort; label: string }[] = [
  { value: "title", label: "Name (A–Z)" },
  { value: "pages", label: "Most pages" },
  { value: "type", label: "Type" },
];

// Curated spotlight shelves that jump to a category filter.
const COLLECTIONS: { label: string; blurb: string; category: string; badge?: string }[] = [
  { label: "Science & Mathematics", blurb: "OpenStax textbooks — calculus, physics, chemistry, biology.", category: "Science & Mathematics", badge: "New" },
  { label: "Survival & Preparedness", blurb: "Field manuals, navigation, shelter, and first aid.", category: "Emergency Preparedness & Survival" },
  { label: "Health & Medicine", blurb: "Medical references, conditions, and emergency care.", category: "Health & Medicine" },
];

const DocCard = memo(function DocCard({
  doc,
  onClick,
  selected = false,
  layout = "list",
}: {
  doc: LibraryDoc;
  onClick: () => void;
  selected?: boolean;
  layout?: "list" | "grid";
}) {
  const meta = TYPE_META[doc.type] ?? TYPE_META.pdf;
  const Icon = docIconFor(doc.type);
  const pages = doc.page_count ? `${doc.page_count} pages` : "";
  const metaBits = [pages, doc.source].filter(Boolean).join(" · ");
  const description = doc.description ? doc.description.trim() : "";

  const ring = selected
    ? "border-accent/40 shadow-lift ring-1 ring-accent/20"
    : "border-line hover:-translate-y-0.5 hover:border-line-strong hover:shadow-card";

  const typePill = (
    <span className={`shrink-0 whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-semibold ${meta.pill}`}>
      {meta.label}
    </span>
  );

  if (layout === "grid") {
    return (
      <div
        role="button"
        tabIndex={0}
        className={`group flex h-full cursor-pointer flex-col rounded-2xl border bg-surface p-4 transition-all duration-200 ease-spring ${ring}`}
        onClick={onClick}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onClick())}
      >
        <div className="mb-3 flex items-center justify-between">
          <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${meta.tint}`}>
            <Icon size={19} />
          </span>
          {typePill}
        </div>
        <div className="line-clamp-2 font-medium text-ink">{doc.title}</div>
        {description && <div className="mt-1.5 line-clamp-3 text-sm text-ink-soft">{description}</div>}
        <div className="mt-auto pt-3 text-xs text-ink-faint nums">
          {metaBits}
          {doc.subcategory && (
            <div className="mt-1.5">
              <span className="rounded-md bg-surface-sunk px-2 py-0.5 font-medium text-ink-soft">{doc.subcategory}</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      className={`group mb-2.5 flex min-h-[110px] cursor-pointer items-center justify-between rounded-2xl border bg-surface px-5 py-4 transition-all duration-200 ease-spring ${ring}`}
      onClick={onClick}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onClick())}
    >
      <div className="flex min-w-0 items-start">
        <span className={`mr-4 mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${meta.tint}`}>
          <Icon size={19} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-ink">{doc.title}</div>
          {description && <div className="mt-1 line-clamp-2 max-w-[640px] text-sm text-ink-soft">{description}</div>}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-faint nums">
            {metaBits}
            {doc.subcategory && (
              <span className="rounded-md bg-surface-sunk px-2 py-0.5 font-medium text-ink-soft">{doc.subcategory}</span>
            )}
          </div>
        </div>
      </div>
      {typePill}
    </div>
  );
});

function CategoryTile({ node, onOpen }: { node: CategoryNode; onOpen: (category: string) => void }) {
  const { Icon, tint } = categoryMeta(node.category);
  const topSubs = node.subcategories.slice(0, 3).map((s) => s.subcategory).join(" · ");
  return (
    <button
      type="button"
      onClick={() => onOpen(node.category)}
      className="group flex items-start gap-4 rounded-2xl border border-line bg-surface p-5 text-left transition-all duration-200 ease-spring hover:-translate-y-0.5 hover:border-line-strong hover:shadow-card"
    >
      <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${tint}`}>
        <Icon size={22} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2">
          <span className="font-medium text-ink">{node.category}</span>
          <ChevronRightIcon size={16} className="shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5" />
        </span>
        <span className="mt-0.5 block text-sm text-ink-faint nums">{node.documents.toLocaleString()} documents</span>
        {topSubs && <span className="mt-1.5 block truncate text-xs text-ink-faint">{topSubs}</span>}
      </span>
    </button>
  );
}

export default function Library() {
  const [categoryTree, setCategoryTree] = useState<CategoryNode[]>([]);
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("");
  const [activeSub, setActiveSub] = useState("");
  const [activeType, setActiveType] = useState<DocFilter>("all");
  const [sort, setSort] = useState<LibrarySort>("title");
  const [layout, setLayout] = useState<"list" | "grid">("list");

  const [docs, setDocs] = useState<LibraryDoc[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<LibraryDoc | null>(null);

  const inResults = Boolean(activeCategory || query || activeType !== "all");
  const totalDocs = useMemo(() => categoryTree.reduce((s, c) => s + c.documents, 0), [categoryTree]);
  const subcategories = useMemo(
    () => categoryTree.find((c) => c.category === activeCategory)?.subcategories ?? [],
    [categoryTree, activeCategory],
  );

  useEffect(() => {
    fetchCategories().then(setCategoryTree).catch(() => setCategoryTree([]));
  }, []);

  // Debounce the search box into the query used for fetching.
  useEffect(() => {
    const t = setTimeout(() => setQuery(queryInput.trim()), 250);
    return () => clearTimeout(t);
  }, [queryInput]);

  const load = useCallback(
    async (reset: boolean, currentOffset: number) => {
      setLoading(true);
      try {
        const typeParam = activeType === "all" ? "" : activeType;
        const data = await fetchLibraryPage(
          query, PAGE, reset ? 0 : currentOffset, activeCategory, activeSub, sort, typeParam,
        );
        setTotal(data.count);
        setDocs((prev) => (reset ? data.documents : [...prev, ...data.documents]));
        setOffset((reset ? 0 : currentOffset) + data.returned);
        setError("");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [query, activeCategory, activeSub, activeType, sort],
  );

  // (Re)load whenever a facet/search/sort changes while in results mode.
  useEffect(() => {
    if (!inResults) {
      setDocs([]);
      setTotal(0);
      setOffset(0);
      return;
    }
    load(true, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, activeCategory, activeSub, activeType, sort, inResults]);

  // Esc closes the reader.
  useEffect(() => {
    if (!selectedDoc) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSelectedDoc(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedDoc]);

  function openCategory(category: string) {
    setActiveCategory(category);
    setActiveSub("");
  }
  function backToOverview() {
    setActiveCategory("");
    setActiveSub("");
    setActiveType("all");
    setQueryInput("");
    setQuery("");
  }

  const activeChips = [
    activeCategory && { label: activeCategory, clear: () => { setActiveCategory(""); setActiveSub(""); } },
    activeSub && { label: activeSub, clear: () => setActiveSub("") },
    activeType !== "all" && { label: TYPE_OPTIONS.find((t) => t.value === activeType)!.label, clear: () => setActiveType("all") },
    query && { label: `“${query}”`, clear: () => { setQueryInput(""); setQuery(""); } },
  ].filter(Boolean) as { label: string; clear: () => void }[];

  return (
    <div className="mx-auto max-w-[1600px] px-6 pb-16 pt-8">
      <Nav />

      <div className="mb-7">
        <h1 className="font-display text-3xl font-semibold tracking-[-0.02em] text-ink">Library</h1>
        <p className="mt-1.5 text-ink-soft nums">
          {totalDocs.toLocaleString()} documents across {categoryTree.length} categories.
        </p>
      </div>

      <div className="relative mb-6 max-w-2xl">
        <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint">
          <SearchIcon size={18} />
        </span>
        <input
          className="w-full box-border rounded-xl border border-line bg-surface py-3.5 pl-11 pr-4 text-base text-ink shadow-inset outline-none transition-colors placeholder:text-ink-faint focus:border-accent/50"
          type="text"
          placeholder="Search the whole library…"
          value={queryInput}
          onChange={(e) => setQueryInput(e.target.value)}
        />
      </div>

      {!inResults ? (
        <div className="space-y-10">
          <section>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint">Featured collections</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {COLLECTIONS.map((c) => {
                const node = categoryTree.find((n) => n.category === c.category);
                if (!node) return null;
                const { Icon, tint } = categoryMeta(c.category);
                return (
                  <button
                    key={c.category}
                    type="button"
                    onClick={() => openCategory(c.category)}
                    className="group flex flex-col rounded-3xl border border-line bg-surface p-6 text-left shadow-card transition-all duration-200 ease-spring hover:-translate-y-0.5 hover:shadow-lift"
                  >
                    <div className="mb-4 flex items-center justify-between">
                      <span className={`flex h-12 w-12 items-center justify-center rounded-2xl ${tint}`}>
                        <Icon size={24} />
                      </span>
                      {c.badge && (
                        <span className="rounded-md bg-accent-soft px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-accent-ink">
                          {c.badge}
                        </span>
                      )}
                    </div>
                    <div className="font-display text-lg font-semibold text-ink">{c.label}</div>
                    <div className="mt-1 text-sm text-ink-soft">{c.blurb}</div>
                    <div className="mt-3 text-xs font-medium text-ink-faint nums">{node.documents.toLocaleString()} documents →</div>
                  </button>
                );
              })}
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint">Browse by category</h2>
            {categoryTree.length === 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="skeleton h-24 rounded-2xl" />)}
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {categoryTree.map((node) => (
                  <CategoryTile key={node.category} node={node} onOpen={openCategory} />
                ))}
              </div>
            )}
          </section>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
          <aside className="lg:sticky lg:top-24 lg:self-start">
            <button
              type="button"
              onClick={backToOverview}
              className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft transition-colors hover:text-accent-ink"
            >
              <ArrowLeftIcon size={16} /> All categories
            </button>

            <div className="mb-5">
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-faint">Category</div>
              <div className="space-y-0.5">
                {categoryTree.map((c) => (
                  <button
                    key={c.category}
                    type="button"
                    onClick={() => openCategory(c.category)}
                    className={[
                      "flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors",
                      activeCategory === c.category ? "bg-ink/[0.06] font-medium text-ink" : "text-ink-soft hover:bg-ink/[0.04] hover:text-ink",
                    ].join(" ")}
                  >
                    <span className="truncate">{c.category}</span>
                    <span className="ml-2 shrink-0 text-xs text-ink-faint nums">{c.documents.toLocaleString()}</span>
                  </button>
                ))}
              </div>
            </div>

            {activeCategory && subcategories.length > 0 && (
              <div className="mb-5">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-faint">Subcategory</div>
                <div className="space-y-0.5">
                  <button
                    type="button"
                    onClick={() => setActiveSub("")}
                    className={[
                      "w-full rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors",
                      !activeSub ? "bg-ink/[0.06] font-medium text-ink" : "text-ink-soft hover:bg-ink/[0.04] hover:text-ink",
                    ].join(" ")}
                  >
                    All
                  </button>
                  {subcategories.map((s) => (
                    <button
                      key={s.subcategory}
                      type="button"
                      onClick={() => setActiveSub(s.subcategory)}
                      className={[
                        "flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors",
                        activeSub === s.subcategory ? "bg-ink/[0.06] font-medium text-ink" : "text-ink-soft hover:bg-ink/[0.04] hover:text-ink",
                      ].join(" ")}
                    >
                      <span className="truncate">{s.subcategory}</span>
                      <span className="ml-2 shrink-0 text-xs text-ink-faint nums">{s.documents.toLocaleString()}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-faint">Type</div>
              <div className="flex flex-wrap gap-1.5">
                {TYPE_OPTIONS.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setActiveType(t.value)}
                    className={[
                      "rounded-lg px-2.5 py-1 text-sm font-medium transition-colors",
                      activeType === t.value ? "bg-ink text-surface" : "text-ink-soft hover:bg-ink/[0.06] hover:text-ink",
                    ].join(" ")}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          </aside>

          <div className="min-w-0">
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <div className="text-sm text-ink-faint nums">
                {loading && docs.length === 0 ? "Loading…" : `${total.toLocaleString()} result${total === 1 ? "" : "s"}`}
              </div>
              <div className="ml-auto flex items-center gap-2">
                <select
                  aria-label="Sort"
                  className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm text-ink-soft transition-colors hover:border-line-strong"
                  value={sort}
                  onChange={(e) => setSort(e.target.value as LibrarySort)}
                >
                  {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                <div className="flex overflow-hidden rounded-lg border border-line">
                  <button
                    type="button"
                    onClick={() => setLayout("list")}
                    className={`px-2 py-1.5 ${layout === "list" ? "bg-ink text-surface" : "bg-surface text-ink-soft hover:text-ink"}`}
                    aria-label="List view"
                  >
                    <ListIcon size={16} />
                  </button>
                  <button
                    type="button"
                    onClick={() => setLayout("grid")}
                    className={`px-2 py-1.5 ${layout === "grid" ? "bg-ink text-surface" : "bg-surface text-ink-soft hover:text-ink"}`}
                    aria-label="Grid view"
                  >
                    <GridIcon size={16} />
                  </button>
                </div>
              </div>
            </div>

            {activeChips.length > 0 && (
              <div className="mb-4 flex flex-wrap items-center gap-2">
                {activeChips.map((chip, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={chip.clear}
                    className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink-soft transition-colors hover:border-line-strong hover:text-ink"
                  >
                    {chip.label}
                    <span className="text-ink-faint">✕</span>
                  </button>
                ))}
              </div>
            )}

            {error && (
              <div className="rounded-xl border border-data-clay/30 bg-data-clay/10 px-4 py-3 text-sm text-data-clay">{error}</div>
            )}

            {!error && !loading && docs.length === 0 && (
              <div className="mt-10 rounded-2xl border border-dashed border-line-strong bg-surface/50 px-6 py-12 text-center">
                <div className="font-display text-lg font-semibold text-ink">No documents match</div>
                <p className="mx-auto mt-1.5 max-w-sm text-sm text-ink-soft">
                  Try a broader search or clear a filter to widen the results.
                </p>
              </div>
            )}

            {loading && docs.length === 0 ? (
              <div className={layout === "grid" ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-3" : ""}>
                {[0, 1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className={`skeleton rounded-2xl ${layout === "grid" ? "h-44" : "mb-2.5 h-[110px]"}`} />
                ))}
              </div>
            ) : (
              <div className={layout === "grid" ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-3" : ""}>
                {docs.map((doc) => (
                  <DocCard
                    key={`${doc.source}-${doc.title}-${doc.open_url}`}
                    doc={doc}
                    layout={layout}
                    selected={selectedDoc?.open_url === doc.open_url}
                    onClick={() => setSelectedDoc(doc)}
                  />
                ))}
              </div>
            )}

            {!error && offset < total && (
              <div className="mt-6 text-center">
                <button
                  className="cursor-pointer rounded-xl border border-line bg-surface px-5 py-2.5 text-sm font-medium text-ink-soft transition-colors hover:border-line-strong hover:text-ink disabled:opacity-50"
                  onClick={() => load(false, offset)}
                  disabled={loading}
                >
                  {loading ? "Loading…" : `Load more (${(total - docs.length).toLocaleString()} left)`}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {selectedDoc && (
        <div className="fixed inset-0 z-40">
          <div className="absolute inset-0 bg-ink/30 backdrop-blur-sm" onClick={() => setSelectedDoc(null)} />
          <aside className="absolute inset-y-0 right-0 flex w-full max-w-4xl flex-col bg-surface shadow-lift">
            <div className="flex items-center justify-between gap-3 border-b border-line bg-surface-sunk px-5 py-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-ink">{selectedDoc.title}</div>
                <div className="truncate text-[11px] uppercase tracking-[0.16em] text-ink-faint">{selectedDoc.type}</div>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={selectedDoc.open_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-surface no-underline transition-colors hover:bg-accent-deep"
                >
                  <ExternalIcon size={14} /> Open
                </a>
                <button
                  className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-soft transition-colors hover:border-line-strong hover:text-ink"
                  onClick={() => setSelectedDoc(null)}
                >
                  Close
                </button>
              </div>
            </div>
            <iframe title={selectedDoc.title} src={selectedDoc.open_url} className="h-full w-full flex-1 border-0 bg-white" />
          </aside>
        </div>
      )}
    </div>
  );
}
