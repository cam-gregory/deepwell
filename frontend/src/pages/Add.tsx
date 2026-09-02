import { useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";
import { CheckIcon } from "../components/Icons";
import {
  previewCrawl,
  startIngestJob,
  streamIngestJob,
  type CrawlPreview,
  type IngestEvent,
} from "../api";

interface StageRow {
  name: string;
  label: string;
  status: "start" | "done";
}

function fmtBytes(b: number): string {
  if (b <= 0) return "unknown";
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(0)} KB`;
  if (b < 1073741824) return `${(b / 1048576).toFixed(1)} MB`;
  return `${(b / 1073741824).toFixed(2)} GB`;
}

// Persisted across route changes (but not across tabs/reloads-to-a-different-app)
// so navigating to Library and back to Add reconnects to the same job instead
// of losing progress — the job itself keeps running server-side regardless.
const ACTIVE_JOB_KEY = "deepwell_active_ingest_job";

export default function Add() {
  const [files, setFiles] = useState<File[]>([]);
  const [urls, setUrls] = useState("");
  const [webLinkPattern, setWebLinkPattern] = useState("");
  const [downloadPdfs, setDownloadPdfs] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [running, setRunning] = useState(false);
  const [stages, setStages] = useState<StageRow[]>([]);
  const [error, setError] = useState("");
  const [finished, setFinished] = useState(false);
  const [preview, setPreview] = useState<CrawlPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | File[]) {
    const pdfs = Array.from(list).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => f.name + f.size));
      const merged = [...prev];
      for (const f of pdfs) {
        if (!seen.has(f.name + f.size)) merged.push(f);
      }
      return merged;
    });
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  }

  function applyEvent(event: IngestEvent) {
    if (event.type === "stage") {
      setStages((prev) => {
        const idx = prev.findIndex((s) => s.name === event.name);
        const row: StageRow = { name: event.name, label: event.label, status: event.status };
        if (idx === -1) return [...prev, row];
        const copy = [...prev];
        copy[idx] = row;
        return copy;
      });
    } else if (event.type === "done") {
      setFinished(true);
    } else if (event.type === "error") {
      throw new Error(event.message);
    }
  }

  // Reconnect to any job left running from before this page was last mounted.
  useEffect(() => {
    const jobId = sessionStorage.getItem(ACTIVE_JOB_KEY);
    if (!jobId) return;

    let cancelled = false;
    setRunning(true);
    setError("");
    setFinished(false);
    setStages([]);

    streamIngestJob(jobId, (event) => {
      if (!cancelled) applyEvent(event);
    })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (cancelled) return;
        setRunning(false);
        sessionStorage.removeItem(ACTIVE_JOB_KEY);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function parseLines(value: string): string[] {
    return value
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
  }

  async function handlePreview() {
    const urlList = parseLines(urls);
    if (urlList.length === 0) {
      setPreviewError("Add at least one URL to preview.");
      return;
    }
    setPreviewing(true);
    setPreviewError("");
    setPreview(null);
    try {
      setPreview(await previewCrawl(urlList, webLinkPattern.trim()));
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : String(err));
    } finally {
      setPreviewing(false);
    }
  }

  async function handleStart() {
    const urlList = parseLines(urls);
    if (files.length === 0 && urlList.length === 0) {
      setError("Add at least one PDF or URL first.");
      return;
    }

    setRunning(true);
    setError("");
    setFinished(false);
    setStages([]);

    try {
      const jobId = await startIngestJob(files, urlList, webLinkPattern.trim(), downloadPdfs);
      sessionStorage.setItem(ACTIVE_JOB_KEY, jobId);
      await streamIngestJob(jobId, applyEvent);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
      sessionStorage.removeItem(ACTIVE_JOB_KEY);
    }
  }

  return (
    <div className="mx-auto max-w-[1600px] px-6 pb-16 pt-8">
      <Nav />

      <div className="mx-auto max-w-3xl">
        <div className="rounded-3xl border border-line bg-surface p-6 shadow-card">
          <div className="mb-4 flex items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-data-gold/12 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-data-gold">
              <span className="h-1.5 w-1.5 rounded-full bg-data-gold" />
              Admin tool
            </span>
            <span className="text-xs font-medium text-ink-faint">Not part of everyday retrieval</span>
          </div>

          <h1 className="font-display text-3xl font-semibold tracking-[-0.02em] text-ink">Add to library</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-soft">
            Ingest new source material into Deepwell. Use Ask and Library for retrieval; this page
            handles indexing and content updates.
          </p>
        </div>

        <div className="mt-6 rounded-3xl border border-line bg-surface p-6 shadow-card">
          <div
            className={
              "cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-200 " +
              (dragOver
                ? "border-accent bg-accent-soft/50 shadow-inset"
                : "border-line-strong bg-surface-sunk/60 hover:border-accent/50 hover:bg-surface-sunk")
            }
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="text-base font-medium text-ink">
              Drag &amp; drop PDF files here, or click to browse
            </div>
            <div className="mt-2 text-sm text-ink-faint">Only PDF documents are accepted.</div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={(e) => e.target.files && addFiles(e.target.files)}
            />
          </div>

          {files.length > 0 && (
            <div className="mt-4 space-y-2">
              {files.map((f, i) => (
                <div
                  key={f.name + f.size}
                  className="flex items-center justify-between rounded-xl border border-line bg-surface-sunk px-4 py-2.5 text-sm text-ink-soft"
                >
                  <span>
                    {f.name} <span className="text-ink-faint nums">({(f.size / 1024).toFixed(0)} KB)</span>
                  </span>
                  <button
                    className="text-ink-faint transition-colors hover:text-data-clay"
                    onClick={() => removeFile(i)}
                    aria-label={`Remove ${f.name}`}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="mt-8 space-y-6">
            <div>
              <label className="mb-2 block text-sm font-medium text-ink">
                Source URLs (one per line)
              </label>
              <div className="mb-2 text-xs leading-5 text-ink-faint">
                Handled automatically by type: <span className="font-mono text-ink-soft">.zim</span>{" "}
                archives are downloaded; any other URL is crawled as a web index, saving every linked
                page as a document.
              </div>
              <textarea
                className="w-full box-border rounded-xl border border-line bg-surface-sunk p-3.5 text-sm font-mono text-ink-soft shadow-inset outline-none transition-colors focus:border-accent/50 focus:bg-surface"
                rows={5}
                placeholder={"https://download.kiwix.org/zim/other/example.zim\nhttps://medlineplus.gov/ency/encyclopedia_A.htm"}
                value={urls}
                onChange={(e) => setUrls(e.target.value)}
              />
              <label className="mb-2 mt-3 block text-sm font-medium text-ink">
                Link filter for crawled sites (optional regex)
              </label>
              <input
                className="w-full box-border rounded-xl border border-line bg-surface-sunk p-3 text-sm font-mono text-ink-soft shadow-inset outline-none transition-colors focus:border-accent/50 focus:bg-surface"
                type="text"
                placeholder="/ency/article/"
                value={webLinkPattern}
                onChange={(e) => setWebLinkPattern(e.target.value)}
              />

              <label className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-line-strong text-accent focus:ring-accent"
                  checked={downloadPdfs}
                  onChange={(e) => setDownloadPdfs(e.target.checked)}
                />
                Also download PDFs linked from crawled pages
              </label>

              <div className="mt-3 flex items-center gap-3">
                <button
                  type="button"
                  className="rounded-xl border border-line bg-surface px-4 py-2 text-sm font-medium text-ink-soft transition-colors hover:border-line-strong hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={handlePreview}
                  disabled={previewing}
                >
                  {previewing ? "Estimating…" : "Preview crawl size"}
                </button>
                <span className="text-xs text-ink-faint">
                  Check how many pages this would add before ingesting.
                </span>
              </div>

              {previewError && (
                <div className="mt-3 rounded-xl border border-data-clay/30 bg-data-clay/10 px-4 py-3 text-sm text-data-clay">
                  {previewError}
                </div>
              )}

              {preview && (
                <div className="mt-3 rounded-xl border border-line bg-surface-sunk p-4 text-sm">
                  <div className="font-medium text-ink nums">
                    Estimated {preview.total_pages} page{preview.total_pages === 1 ? "" : "s"} · ~
                    {fmtBytes(preview.total_estimated_bytes)} on disk
                  </div>
                  <div className="mt-1 text-xs text-ink-faint">
                    Rough estimate from sampling a few pages. Actual indexed count may be lower —
                    navigation and list pages are filtered out during ingest.
                  </div>
                  <div className="mt-3 space-y-1.5">
                    {preview.previews.map((p) => (
                      <div key={p.url} className="flex items-baseline justify-between gap-4">
                        <span className="min-w-0 truncate font-mono text-xs text-ink-soft">{p.url}</span>
                        <span className="shrink-0 text-xs text-ink-faint nums">
                          {p.kind === "zim"
                            ? `ZIM archive · ~${fmtBytes(p.estimated_bytes)}`
                            : `${p.pages} page${p.pages === 1 ? "" : "s"} · ~${fmtBytes(p.estimated_bytes)}`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="mt-8 flex items-center gap-3">
            <button
              className="rounded-xl bg-accent px-6 py-3 text-base font-medium text-surface shadow-card transition-all duration-200 ease-spring hover:bg-accent-deep active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
              onClick={handleStart}
              disabled={running}
            >
              {running ? "Running…" : "Start ingest"}
            </button>
            <span className="text-xs uppercase tracking-[0.16em] text-ink-faint">Indexing pipeline</span>
          </div>

          {error && (
            <div className="mt-6 rounded-xl border border-data-clay/30 bg-data-clay/10 px-4 py-3 text-sm text-data-clay">
              {error}
            </div>
          )}

          {stages.length > 0 && (
            <div className="mt-8 rounded-2xl border border-line bg-surface-sunk p-5">
              {stages.map((s) => (
                <div key={s.name} className="flex items-center gap-3 py-1.5 text-sm text-ink-soft">
                  {s.status === "done" ? (
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-soft text-accent-ink">
                      <CheckIcon size={13} />
                    </span>
                  ) : (
                    <span className="flex h-5 w-5 items-center justify-center">
                      <span className="h-2.5 w-2.5 animate-pulse-soft rounded-full bg-data-gold" />
                    </span>
                  )}
                  <span>{s.label}</span>
                </div>
              ))}
              {finished && (
                <div className="mt-3 flex items-center gap-2 border-t border-line pt-3 text-sm font-medium text-accent-ink">
                  <CheckIcon size={15} />
                  Done — new documents are searchable now.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
