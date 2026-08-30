import { useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";
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

      <div className="rounded-3xl border border-amber-200 bg-gradient-to-br from-amber-50 via-white to-slate-50 p-6 shadow-sm ring-1 ring-slate-200/70">
        <div className="mb-4 flex items-center gap-3">
          <span className="rounded-full bg-amber-200 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-900">
            Admin tool
          </span>
          <span className="text-xs font-medium text-slate-500">Not part of everyday retrieval</span>
        </div>

        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Add to Library</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          This workflow ingests new source material into Deepwell. Use Ask and Library for
          information retrieval; this page is for indexing and content updates.
        </p>
      </div>

      <div className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm ring-1 ring-slate-200/70">
        <div
          className={
            "cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all " +
            (dragOver
              ? "border-slate-900 bg-slate-50 shadow-inner"
              : "border-slate-300 bg-slate-50/60 hover:border-slate-400 hover:bg-slate-50")
          }
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="text-base font-medium text-slate-700">
            Drag &amp; drop PDF files here, or click to browse
          </div>
          <div className="mt-2 text-sm text-slate-500">Only PDF documents are accepted.</div>
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
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-700"
              >
                <span>
                  {f.name} <span className="text-slate-400">({(f.size / 1024).toFixed(0)} KB)</span>
                </span>
                <button
                  className="text-slate-400 transition hover:text-red-600"
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
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Source URLs (one per line)
            </label>
            <div className="mb-2 text-xs leading-5 text-slate-500">
              Handled automatically by type: <span className="font-mono">.zim</span> archives are
              downloaded; any other URL is crawled as a web index, saving every linked page as a
              document.
            </div>
            <textarea
              className="w-full box-border rounded-xl border border-slate-300 bg-slate-50 p-3.5 text-sm font-mono text-slate-700 shadow-inner outline-none transition focus:border-slate-400 focus:bg-white"
              rows={5}
              placeholder={"https://download.kiwix.org/zim/other/example.zim\nhttps://medlineplus.gov/ency/encyclopedia_A.htm"}
              value={urls}
              onChange={(e) => setUrls(e.target.value)}
            />
            <label className="mt-3 mb-2 block text-sm font-medium text-slate-700">
              Link filter for crawled sites (optional regex)
            </label>
            <input
              className="w-full box-border rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm font-mono text-slate-700 shadow-inner outline-none transition focus:border-slate-400 focus:bg-white"
              type="text"
              placeholder="/ency/article/"
              value={webLinkPattern}
              onChange={(e) => setWebLinkPattern(e.target.value)}
            />

            <label className="mt-3 flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300"
                checked={downloadPdfs}
                onChange={(e) => setDownloadPdfs(e.target.checked)}
              />
              Also download PDFs linked from crawled pages
            </label>

            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={handlePreview}
                disabled={previewing}
              >
                {previewing ? "Estimating…" : "Preview crawl size"}
              </button>
              <span className="text-xs text-slate-500">
                Check how many pages this would add before ingesting.
              </span>
            </div>

            {previewError && (
              <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {previewError}
              </div>
            )}

            {preview && (
              <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
                <div className="font-medium text-slate-800">
                  Estimated {preview.total_pages} page{preview.total_pages === 1 ? "" : "s"} ·
                  ~{fmtBytes(preview.total_estimated_bytes)} on disk
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  Rough estimate from sampling a few pages. Actual indexed count may be lower —
                  navigation and list pages are filtered out during ingest.
                </div>
                <div className="mt-3 space-y-1.5">
                  {preview.previews.map((p) => (
                    <div key={p.url} className="flex items-baseline justify-between gap-4">
                      <span className="min-w-0 truncate font-mono text-xs text-slate-600">{p.url}</span>
                      <span className="shrink-0 text-xs text-slate-500">
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
            className="rounded-xl bg-slate-900 px-6 py-3 text-base font-medium text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={handleStart}
            disabled={running}
          >
            {running ? "Running…" : "Start ingest"}
          </button>
          <span className="text-xs uppercase tracking-[0.18em] text-slate-400">Indexing pipeline</span>
        </div>

        {error && <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">{error}</div>}

        {stages.length > 0 && (
          <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50 p-5">
            {stages.map((s) => (
              <div key={s.name} className="flex items-center gap-3 py-1.5 text-sm text-slate-700">
                <span>{s.status === "done" ? "✅" : "⏳"}</span>
                <span>{s.label}</span>
              </div>
            ))}
            {finished && (
              <div className="mt-3 border-t border-slate-200 pt-3 text-sm font-medium text-emerald-700">
                Done — new documents are searchable now.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
