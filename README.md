# Deepwell

**Deepwell** is a fully offline retrieval-augmented question-answering app over a personal document library. It ingests PDFs and Kiwix ZIM archives, indexes them for hybrid semantic + keyword search, and answers questions with a local LLM — with inline source citations, streaming responses, and a browsable document library. Everything runs on your machine with no network calls at query time.

## What It Does

* Ask a natural-language question and get a Markdown-formatted answer grounded only in your own documents, with `[Source N]` citations.
* Answers stream token-by-token as the model generates them.
* Browse every document and article in the corpus in a Library view, and open the original PDF or ZIM article in the browser.
* All inference is local via Ollama; all data lives in a local SQLite database plus a FAISS index.

## Architecture Overview

The system is two halves: an offline ingestion pipeline that builds the search corpus, and a runtime API/UI that serves answers from it.

```
                       INGESTION (offline, run when docs change)
  data/sources/pdf/*.pdf ─┐
  data/sources/zim/*.zim ─┤
                          ▼
   pdf_reader / zim_reader  → data/extracted/*.json   (one JSON per document/article)
                          ▼
   metadata (describe_all)  → adds display_title + description
                          ▼
   chunker                  → data/chunks/*_chunks.json
                          ▼
   enricher                 → data/enriched/*_enriched.json  (keywords, content_type, difficulty)
                          ▼
   db_loader                → SQLite: documents, chunks, chunks_fts (FTS5)
                          ▼
   vector_index             → FAISS index + writes faiss_row back into SQLite

                       RUNTIME (serves the app)
   Browser ──HTTP──▶ FastAPI (main.py)
                       ├─ /ask     → search() → LLM (Ollama) → streamed answer
                       ├─ /search  → search() (debug/raw results)
                       ├─ /library → Library UI (SQL-backed list)
                       ├─ /pdf/…   → serves a PDF inline
                       └─ /zim/…   → serves a ZIM article/asset live from the .zim
```

Retrieval is a two-stage hybrid: FAISS dense vectors and SQLite FTS5 keyword search each recall candidates, the candidate pool is de-duplicated, then a cross-encoder reranker scores every candidate against the query and keeps the top few for the LLM.

## Project Structure

```
deepwell/
├── app/
│   ├── main.py            FastAPI app: routes for ask, search, library, pdf, zim, debug
│   ├── config.py          Single source of truth for all paths and settings
│   ├── db.py              SQLite schema + query helpers (documents, chunks, FTS5)
│   ├── search.py          Hybrid retrieval (FAISS dense + FTS5) + cross-encoder rerank
│   ├── answer.py          Prompt assembly + streaming answer orchestration
│   ├── model.py           Ollama client (generate + generate_stream)
│   ├── ingest.py          Background ingest job runner (upload → pipeline stages → NDJSON progress)
│   └── static/            Built frontend output (generated, do not edit by hand)
├── frontend/               React + TypeScript + Tailwind UI (source for app/static/)
│   ├── src/
│   │   ├── pages/          Ask.tsx, Library.tsx, Debug.tsx, Add.tsx
│   │   ├── components/     Nav.tsx, Markdown.tsx (offline markdown renderer)
│   │   └── api.ts          Fetch helpers for /ask, /search, /library/list, /ingest, etc.
│   └── vite.config.ts      Builds to ../app/static with base path /static/
├── ingestion/
│   ├── pdf_reader.py       PDF → extracted JSON (content-hash skip cache)
│   ├── zim_downloader.py   Stream a .zim from a Kiwix URL into data/sources/zim/
│   ├── zim_reader.py       ZIM → one extracted JSON per article/book
│   ├── web_reader.py       Crawl a web article index page → one extracted JSON per linked article
│   ├── http_client.py      PAC-aware proxy resolution for ZIM/web downloads (corporate VPNs)
│   ├── metadata.py         LLM-generated display_title + description
│   ├── chunker.py          Split documents into overlapping-safe text chunks
│   ├── enricher.py         Add keywords / content_type / difficulty to chunks
│   ├── db_loader.py        Load extracted + enriched JSON into SQLite
│   └── vector_index.py     Embed chunks → FAISS, record faiss_row in SQLite
├── run_pipeline.py         Runs the full ingestion pipeline end to end
└── data/
    ├── sources/pdf/        Drop PDFs here
    ├── sources/zim/        Downloaded .zim files (+ .catalog.json, .manifest.json)
    ├── sources/web/        Offline HTML snapshots of crawled web articles (served at /web/...)
    ├── extracted/          Per-document JSON (+ .manifest.json for PDF hashing)
    ├── chunks/             Chunked JSON
    ├── enriched/           Enriched chunk JSON
    ├── vectorstore/        knowledge.index (FAISS)
    └── knowledge.db        SQLite database (documents, chunks, FTS5)
```

## Prerequisites

* Python 3.10+ with a virtual environment.
* [Ollama](https://ollama.com) installed and running locally.
* Python packages: `fastapi`, `uvicorn`, `httpx`, `sentence-transformers`, `faiss-cpu`, `PyMuPDF` (`fitz`), `libzim`, `beautifulsoup4`. (`rank_bm25` is no longer needed — keyword search is handled by SQLite FTS5.)

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn httpx sentence-transformers faiss-cpu PyMuPDF libzim beautifulsoup4
```

## Model Setup (Ollama)

The app uses a non-reasoning instruction model so answers stream immediately with no chain-of-thought to strip out.

```bash
ollama pull llama3.1:8b
```

The model name and generation settings live in `app/config.py` (`MODEL_NAME`, `NUM_CTX`, `NUM_PREDICT`, `TEMPERATURE`, `KEEP_ALIVE`). Keep `NUM_CTX` sized to the prompt (4096 is plenty for a handful of retrieved chunks) rather than the model's maximum — an oversized context window inflates memory and latency for no benefit.

## Adding Documents

### PDFs

Drop `.pdf` files into `data/sources/pdf/` and run the pipeline. Extraction is cached by a SHA-256 of each file's bytes, so unchanged PDFs are skipped on subsequent runs.

### ZIM archives (Kiwix)

Download a `.zim` into `data/sources/zim/`, either manually or with the downloader:

```bash
python -m ingestion.zim_downloader https://download.kiwix.org/zim/other/zimgit-medicine_en_2024-08.zim
```

Notes on ZIMs:

* A `.zim` is a single archive containing many entries. The reader explodes it into one extracted document (and one Library card) per article or book.
* Collection-style ZIMs (like the Medicine library) store their real content as embedded PDF entries, with HTML pages that are just the search UI. The reader extracts the PDF entries and skips viewer chrome (`home`, `search`, images, JS, CSS, etc.).
* The `.zim` stays on disk so articles can be read live in the browser via `/zim/…`.
* Verify a download with its published `.sha256` before ingesting large files.

### Web articles (crawled)

Point the crawler at a listing/index page (e.g. `https://medlineplus.gov/ency/encyclopedia_A.htm`); it follows same-site links from that page, extracts each linked article's text, and saves a fully offline HTML snapshot for reading later — no browser round-trip to the source site required:

```bash
python -m ingestion.web_reader https://medlineplus.gov/ency/encyclopedia_A.htm "/ency/article/"
```

The second argument is an optional regex narrowing which links count as articles (matched against the absolute URL); omit it to follow every same-site link on the page. Notes:

* Each article's extracted text is rendered into a clean, app-styled HTML page under `data/sources/web/` (filename derived deterministically from the URL) and served locally at `/web/<slug>.html` — the Library's "open" link points there, not at the live site, so reading an article needs no network access. A small attribution line links back to the original URL for reference only.
* `source_file` stores the article's original URL (used for de-duplication and citation); the offline snapshot filename is derived from it on the fly, so no extra DB column is needed.
* Already-crawled URLs are skipped on repeat runs (tracked in `data/extracted/.web_manifest.json`); pass `force=True` (or re-run via the `/add` UI, which always accepts new pages) to re-fetch.
* Pages under ~200 characters of extracted text are treated as navigation/chrome, not articles, and skipped.
* A short delay is added between article fetches to be polite to the source site; this is not a general-purpose crawler and does not follow pagination or robots.txt — point it at one listing page at a time.

## Running the Pipeline

Always run from the project root so the `app` and `ingestion` packages both resolve.

```bash
python run_pipeline.py
```

This runs: download ZIMs → crawl web article indexes → extract PDFs → extract ZIMs → describe (titles/descriptions) → chunk → enrich → load into SQLite → build FAISS index. Curated ZIM URLs and web indexes live in `ZIM_URLS` / `WEB_SOURCES` at the top of `run_pipeline.py`.

To run a single stage:

```bash
python -m ingestion.pdf_reader          # extract PDFs
python -m ingestion.zim_reader          # extract ZIMs
python -m ingestion.web_reader <url>    # crawl a web article index
python -m ingestion.db_loader           # JSON → SQLite
python -m ingestion.vector_index        # embed → FAISS + write faiss_row
```

Rule of thumb for the `-m` prefix: it mirrors the folder. Anything in `app/` runs as `python -m app.<name>`; anything in `ingestion/` runs as `python -m ingestion.<name>`.

## Running the App

The UI is a React SPA (`frontend/`) that builds into `app/static/`, which FastAPI serves directly. Build it once (or after any frontend change):

```bash
cd frontend
npm install   # first time only
npm run build # outputs to ../app/static
cd ..
```

Then start the backend as usual:

```bash
uvicorn app.main:app --reload
```

Then open:

* `http://127.0.0.1:8000/` — Ask
* `http://127.0.0.1:8000/library` — Library
* `http://127.0.0.1:8000/debug` — Retrieval debug view

All three paths are served from the same built `index.html`; `react-router` handles routing client-side.

### Frontend development

For hot-reloading UI work, run the Vite dev server alongside the backend instead of rebuilding on every change:

```bash
# terminal 1
uvicorn app.main:app --reload
# terminal 2
cd frontend && npm run dev
```

Open `http://localhost:5173` — Vite proxies `/ask`, `/search`, `/debug/search`, `/library/list`, `/pdf`, and `/zim` to the FastAPI backend on port 8000 (see `frontend/vite.config.ts`).

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serves the Ask UI (React SPA `index.html`) |
| `/health` | GET | Liveness check |
| `/ask` | POST | Conversation-aware; body `{messages:[{role,content}], limit}`. Streams an NDJSON answer: sources → tokens → timings → done |
| `/search?q=&limit=` | GET | Raw retrieval results as JSON |
| `/debug/search?q=&limit=` | GET | Per-candidate dense rank, FTS rank, and rerank score |
| `/debug` | GET | Debug UI: inspect rerank reordering of candidates |
| `/library` | GET | Library UI (same SPA, client-side routed) |
| `/library/list?q=&limit=&offset=` | GET | SQL-backed, paginated document list |
| `/add` | GET | Add-to-library UI: drag-drop PDFs, paste source URLs (ZIM + web, routed by type), crawl web article indexes (same SPA) |
| `/ingest/start` | POST | Multipart form (`files`, `urls`, `web_link_pattern`, `download_pdfs`); saves PDFs, routes each URL by type (`.zim` download vs. web crawl), starts a background ingest job, returns `{job_id}` |
| `/ingest/preview` | POST | Multipart form (`urls`, `web_link_pattern`); estimates page count + disk size per URL (web crawl sampled; `.zim` via HEAD) before ingesting |
| `/ingest/stream/{job_id}` | GET | NDJSON stream of ingest stage progress for a job |
| `/pdf/{filename}` | GET | Serves a PDF inline (path-traversal guarded) |
| `/web/{filename}` | GET | Serves a saved offline HTML snapshot of a crawled web article |
| `/zim/{zim_file}/{article_path}` | GET | Serves a ZIM entry live from the archive |

## Adding Documents from the UI

The `/add` page lets you drag-and-drop PDF files, paste Kiwix `.zim` URLs, and paste web article index URLs (one per line each, plus an optional regex to filter which links on a web index page count as articles), then runs the full ingestion pipeline (crawl/extract → describe → chunk → enrich → load into SQLite → build FAISS index) in a background thread, streaming stage-by-stage progress to the page. When it finishes, the running server reloads its in-memory FAISS index/chunk map (`search.reload_index()`) so new content is searchable immediately — no restart needed. This is equivalent to running `python run_pipeline.py`, just triggered per-upload instead of over the whole `ZIM_URLS`/`WEB_SOURCES` lists.

## How Retrieval Works

1. Recall — the query is embedded (MiniLM) and searched against FAISS for dense candidates; in parallel, SQLite FTS5 returns BM25 keyword candidates. Hybrid recall catches both semantic matches and exact terms (dosages, chemical names, proper nouns) that pure vectors miss.
2. Merge — the two candidate lists are unioned and de-duplicated.
3. Rerank — a cross-encoder scores each `(query, chunk)` pair and keeps the top `FINAL_LIMIT`. This is the biggest quality lever: it promotes genuinely relevant chunks and drops merely-similar ones before they reach the model.

The `/debug` view shows each candidate's dense rank, FTS rank, movement, and rerank score so you can see the reranker working and diagnose whether a weak answer is a recall, ranking, or content problem.

## How Answering Works

`answer.py` retrieves the top chunks, builds a grounded prompt (a system message with the answer rules, and a user message with a Markdown formatting guide plus the retrieved source text), and streams the model's output. Generation runs against Ollama's `/api/chat` endpoint. The answer is emitted as NDJSON events so the UI can render sources first, then stream the answer, then show timing (retrieval, time-to-first-token, generation, total).

## Data Model

SQLite (`data/knowledge.db`) holds all text and metadata; FAISS holds the embeddings. They are joined by `faiss_row`.

* `documents` — one row per PDF or ZIM article: source type, files, titles, description, page count, and the `open_url` used by the Library.
* `chunks` — one row per text chunk, with page range, enrichment metadata, ZIM link fields, and a `faiss_row` that maps to the chunk's position in the FAISS index.
* `chunks_fts` — an FTS5 virtual table mirroring chunk text; this is the persisted BM25 keyword index (replaces the old in-memory `rank_bm25` rebuild).

The original PDFs and `.zim` files stay on disk regardless — the DB stores derived text, and the `/pdf` and `/zim` routes serve the originals for reading.

## Operational Notes and Gotchas

* Run everything from the project root. Both `python run_pipeline.py` and `python -m …` depend on `app` and `ingestion` being importable as packages (each needs an `__init__.py`).
* Force after a code change. The PDF and ZIM extractors skip files whose content is unchanged. If you change reader logic (not the file), the cache will skip it. Use `--force` (e.g. `python -m ingestion.zim_reader --force`) or bump the reader version to invalidate. The ZIM manifest records a `reader_version` so a version bump auto-invalidates.
* Run order matters. `db_loader` must run before `vector_index`, because the index build reads chunks from SQLite and writes each chunk's `faiss_row` back. If `/search` returns nothing after a clean start, check that every chunk has a non-null `faiss_row`.
* Populate the DB before starting the server. `search.py` builds its FAISS-row → chunk-id map at import time; an empty DB means no matches.

## Verifying State

```bash
sqlite3 data/knowledge.db "
SELECT source_type, COUNT(*) FROM documents GROUP BY source_type;
SELECT COUNT(*) FROM chunks;
SELECT COUNT(*) FROM chunks WHERE faiss_row IS NOT NULL;"
```

The chunk count and the `faiss_row IS NOT NULL` count should match exactly — that confirms every chunk is reachable at query time.

## Troubleshooting

* Answer streams reasoning / `<think>` text — you're on a reasoning model or forced thinking off in a way that leaks it into content. Use `llama3.1:8b` (non-reasoning) and don't send `think: false` to a hybrid model.
* Empty answer, HTTP 200 — generation was truncated before producing content (usually reasoning consuming the token budget). Raise `NUM_PREDICT`, or use a non-reasoning model.
* Library shows filenames instead of titles — the metadata step didn't run or the list route isn't reading `display_title`. Re-run `describe_all` / `db_loader`.
* ZIM extracts one junk "article" — the reader matched only the viewer shell. Confirm content mimetypes inside the archive and ensure PDF entries are being read.
* Slow first response — model load/warm-up. Raise `KEEP_ALIVE` or pre-warm; per-token speed is fine once loaded and fully on GPU.
* ZIM/web ingest fails with `[Errno 8] nodename nor servname provided, or not known` — the OS resolver can't reach the public internet directly (common on a corporate VPN/Zscaler-managed machine that routes traffic through a local PAC-configured proxy, which is why a browser still works). `ingestion/http_client.py` auto-detects and uses the system's PAC proxy (via `pypac`) for ZIM/web fetches, so this should self-resolve; if it still fails, the PAC may specify TLS interception with a corporate root CA that Python's bundled `certifi` store doesn't trust (even though `curl`/the browser do, via the OS trust store) — `pip-system-certs` (already in `requirements.txt`) fixes that by making Python use the OS certificate store instead.

## Roadmap

* Incremental embedding — add a `content_hash` column per chunk and skip re-embedding unchanged chunks, so rebuilds don't reprocess the whole corpus.
* Readers writing straight to SQLite — drop the per-article JSON layer once large HTML ZIMs (thousands+ of articles) are in play, to avoid a file-count explosion.
* Metadata pre-filtering — use enrichment metadata (content_type, keywords) to narrow the reranker's candidate pool at scale.
