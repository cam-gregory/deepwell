export interface SearchResult {
  [key: string]: unknown;
}

export interface Source {
  id: number;
  source_file: string;
  page_start: number;
  page_end: number;
}

export interface Timings {
  retrieval: number;
  time_to_first_token: number | null;
  generation: number;
  total: number;
}

export type AskEvent =
  | { type: "sources"; sources: Source[] }
  | { type: "token"; text: string }
  | { type: "timings"; timings: Timings }
  | { type: "error"; message: string };

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/** Streams newline-delimited JSON events from /ask, calling onEvent for each parsed line. */
export async function streamAsk(
  messages: ChatMessage[],
  onEvent: (event: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.trim()) continue;
      onEvent(JSON.parse(line) as AskEvent);
    }
  }
}

export interface LibraryDoc {
  type: string;
  open_url: string;
  title: string;
  description: string;
  page_count: number | null;
  size_bytes: number | null;
  indexed: boolean;
  source: string;
  category: string | null;
  subcategory: string | null;
}

export interface LibraryPage {
  count: number;
  returned: number;
  offset: number;
  limit: number;
  documents: LibraryDoc[];
}

export async function fetchLibraryPage(
  q: string,
  limit: number,
  offset: number,
  category = "",
  subcategory = "",
): Promise<LibraryPage> {
  const params = new URLSearchParams({ q, limit: String(limit), offset: String(offset) });
  if (category) params.set("category", category);
  if (subcategory) params.set("subcategory", subcategory);
  const r = await fetch(`/library/list?${params.toString()}`);
  if (!r.ok) throw new Error(`Request failed: ${r.status}`);
  return r.json();
}

export interface CategorySubNode {
  subcategory: string;
  documents: number;
}
export interface CategoryNode {
  category: string;
  documents: number;
  subcategories: CategorySubNode[];
}

export async function fetchCategories(): Promise<CategoryNode[]> {
  const r = await fetch("/categories");
  if (!r.ok) throw new Error(`Request failed: ${r.status}`);
  const data = await r.json();
  return data.categories as CategoryNode[];
}

export async function fetchDebugSearch(q: string, limit: number): Promise<unknown> {
  const url = `/debug/search?q=${encodeURIComponent(q)}&limit=${limit}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Request failed: ${r.status}`);
  return r.json();
}

export interface CorpusStats {
  documents: number;
  chunks: number;
  pages: number;
  by_source_type: { type: string; documents: number }[];
  by_top_category: { category: string; documents: number }[];
  by_category: { category: string; label: string; chunks: number }[];
  size: {
    pdf_bytes: number;
    zim_bytes: number;
    web_bytes: number;
    sources_bytes: number;
    database_bytes: number;
    vector_bytes: number;
    total_bytes: number;
  };
}

export async function fetchStats(): Promise<CorpusStats> {
  const r = await fetch("/stats");
  if (!r.ok) throw new Error(`Request failed: ${r.status}`);
  return r.json();
}

export interface IngestStageEvent {
  type: "stage";
  name: string;
  label: string;
  status: "start" | "done";
}
export type IngestEvent =
  | IngestStageEvent
  | { type: "done" }
  | { type: "error"; message: string };

export interface CrawlPreviewItem {
  url: string;
  kind: "web" | "zim";
  pages: number;
  sampled: number;
  avg_article_bytes: number;
  estimated_bytes: number;
}

export interface CrawlPreview {
  previews: CrawlPreviewItem[];
  total_pages: number;
  total_estimated_bytes: number;
}

/** Estimates page count + rough disk cost of the given source URLs (web crawl or .zim download). */
export async function previewCrawl(
  urls: string[],
  webLinkPattern: string,
): Promise<CrawlPreview> {
  const form = new FormData();
  form.append("urls", urls.join("\n"));
  form.append("web_link_pattern", webLinkPattern);

  const r = await fetch("/ingest/preview", { method: "POST", body: form });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `Request failed: ${r.status}`);
  return data as CrawlPreview;
}

/** Uploads PDFs + source URLs and starts a background ingest job; returns the job_id. */
export async function startIngestJob(
  files: File[],
  urls: string[],
  webLinkPattern: string,
  downloadPdfs: boolean,
): Promise<string> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  form.append("urls", urls.join("\n"));
  form.append("web_link_pattern", webLinkPattern);
  form.append("download_pdfs", String(downloadPdfs));

  const r = await fetch("/ingest/start", { method: "POST", body: form });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `Request failed: ${r.status}`);
  return data.job_id as string;
}

/** Streams newline-delimited JSON progress events for a running ingest job. */
export async function streamIngestJob(
  jobId: string,
  onEvent: (event: IngestEvent) => void,
): Promise<void> {
  const response = await fetch(`/ingest/stream/${jobId}`);
  if (!response.ok || !response.body) {
    throw new Error(`Request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.trim()) continue;
      onEvent(JSON.parse(line) as IngestEvent);
    }
  }
}
