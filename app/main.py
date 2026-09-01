import re
from pathlib import Path
from urllib.parse import quote, unquote
import base64
import secrets

from fastapi import FastAPI, File, Form, Query, Response, UploadFile
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config
from app import db
from app.ingest import start_ingest_job, stream_job
from app.search import search, search_debug
from app.answer import answer_question_stream

app = FastAPI(
    title="Deepwell",
    version="0.1.0",
)

# Paths always reachable without the shared password (load-balancer health checks).
_AUTH_EXEMPT_PATHS = {"/health"}

def _password_ok(auth_header: str | None) -> bool:
    """True if the HTTP Basic header carries the configured password (any username)."""
    if not auth_header or not auth_header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
    except Exception:
        return False
    _, _, password = decoded.partition(":")
    return secrets.compare_digest(password, config.AUTH_PASSWORD)

@app.middleware("http")
async def require_password(request, call_next):
    """Gate every route behind a shared password when DEEPWELL_PASSWORD is set.
    No password configured => fully open (local dev behaviour is unchanged)."""
    if config.AUTH_PASSWORD and request.url.path not in _AUTH_EXEMPT_PATHS:
        if not _password_ok(request.headers.get("authorization")):
            return Response(
                content="Authentication required",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Deepwell"'},
            )
    return await call_next(request)

class ChatMessage(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    limit: int = Field(5, ge=1, le=20)

# app/static/  ->  index.html, library.html, and any CSS/JS/image assets
STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

# Cache of opened ZIM archives (reads are safe; avoids reopening large files).
_zim_archives: dict[str, object] = {}

def _get_archive(zim_file: str):
    from libzim.reader import Archive
    if zim_file not in _zim_archives:
        root = config.ZIM_SOURCE_DIR.resolve()
        zim_path = (root / Path(zim_file).name).resolve()
        if root not in zim_path.parents or not zim_path.is_file():
            return None
        _zim_archives[zim_file] = Archive(str(zim_path))
    return _zim_archives[zim_file]

@app.get("/")
def root():
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return JSONResponse(
        {"status": "ok", "message": "Deepwell API is running (index.html not found)"}
    )

@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}

@app.get("/search")
def semantic_search(
    q: str = Query(..., min_length=1, description="Semantic search query"),
    limit: int = Query(5, ge=1, le=20),
) -> dict:
    results = search(q, limit)
    return {
        "query": q,
        "result_count": len(results),
        "results": results,
    }

@app.get("/debug/search")
def debug_search(
    q: str = Query(..., min_length=1, description="Query to inspect"),
    limit: int = Query(5, ge=1, le=20),
) -> dict:
    """Raw JSON: dense rank, FTS rank, and rerank score per candidate."""
    return search_debug(q, limit)

@app.get("/debug", response_class=HTMLResponse)
def debug_page():
    return FileResponse(INDEX_HTML)

@app.post("/ask")
def ask(req: AskRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    return StreamingResponse(
        answer_question_stream(messages, req.limit),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/library", response_class=HTMLResponse)
def library_page():
    return FileResponse(INDEX_HTML)

@app.get("/add", response_class=HTMLResponse)
def add_page():
    return FileResponse(INDEX_HTML)

@app.get("/library/list")
def library_list(
    q: str = Query(""),
    category: str = Query(""),
    subcategory: str = Query(""),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    """PDFs (one card each) + ZIM articles (one card each) from the documents table."""
    conditions, params = [], []
    if q:
        conditions.append("(display_title LIKE ? OR description LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if category:
        conditions.append("category = ?")
        params.append(category)
    if subcategory:
        conditions.append("subcategory = ?")
        params.append(subcategory)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with db.connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM documents {where}", params
        ).fetchone()["c"]
        rows = conn.execute(
            f"""SELECT source_type, source_file, display_title, description,
                       page_count, open_url, category, subcategory
                FROM documents {where}
                ORDER BY CASE source_type
                    WHEN 'pdf' THEN 0
                    WHEN 'zim' THEN 1
                    WHEN 'web' THEN 2
                    ELSE 3
                END, display_title
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

    docs = [
        {
            "type": r["source_type"],
            "open_url": r["open_url"],
            "title": r["display_title"],
            "description": r["description"] or "",
            "page_count": r["page_count"],
            "size_bytes": None,
            "indexed": True,
            "source": r["source_file"],
            "category": r["category"],
            "subcategory": r["subcategory"],
        }
        for r in rows
    ]

    return {
        "count": total,
        "returned": len(docs),
        "offset": offset,
        "limit": limit,
        "documents": docs,
    }

@app.get("/categories")
def categories() -> dict:
    """The document taxonomy actually present in the corpus: top-level
    categories, each with their subcategories and document counts."""
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT category, subcategory, COUNT(*) AS c
               FROM documents
               WHERE category IS NOT NULL
               GROUP BY category, subcategory"""
        ).fetchall()

    tree: dict[str, dict] = {}
    for r in rows:
        node = tree.setdefault(r["category"], {"category": r["category"], "documents": 0, "subcategories": []})
        node["documents"] += r["c"]
        if r["subcategory"]:
            node["subcategories"].append({"subcategory": r["subcategory"], "documents": r["c"]})

    categories = sorted(tree.values(), key=lambda n: n["documents"], reverse=True)
    for node in categories:
        node["subcategories"].sort(key=lambda s: s["documents"], reverse=True)

    return {"categories": categories}

def _dir_size(path: Path) -> int:
    """Total size in bytes of all files under path (0 if it doesn't exist)."""
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

# Human-friendly labels for the rule-based content_type buckets from the enricher.
_CATEGORY_LABELS = {
    "procedure": "Procedures & instructions",
    "warning": "Warnings & cautions",
    "definition": "Definitions",
    "scientific_explanation": "Scientific explanations",
    "general_information": "General information",
}

@app.get("/stats")
def stats() -> dict:
    """Corpus overview: document/chunk totals, source-type and information-category
    breakdowns, and on-disk size of the underlying data."""
    with db.connect() as conn:
        doc_total = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()["c"]
        chunk_total = conn.execute("SELECT COUNT(*) AS c FROM chunks").fetchone()["c"]
        page_total = conn.execute(
            "SELECT COALESCE(SUM(page_count), 0) AS c FROM documents"
        ).fetchone()["c"]
        by_source = conn.execute(
            "SELECT source_type, COUNT(*) AS c FROM documents "
            "GROUP BY source_type ORDER BY c DESC"
        ).fetchall()
        by_topcat = conn.execute(
            "SELECT category, COUNT(*) AS c FROM documents "
            "WHERE category IS NOT NULL GROUP BY category ORDER BY c DESC"
        ).fetchall()
        by_category = conn.execute(
            "SELECT content_type, COUNT(*) AS c FROM chunks "
            "GROUP BY content_type ORDER BY c DESC"
        ).fetchall()

    pdf_bytes = _dir_size(config.PDF_SOURCE_DIR)
    zim_bytes = _dir_size(config.ZIM_SOURCE_DIR)
    web_bytes = _dir_size(config.WEB_SOURCE_DIR)
    db_bytes = config.DB_PATH.stat().st_size if config.DB_PATH.exists() else 0
    vector_bytes = _dir_size(config.VECTOR_DIR)

    return {
        "documents": doc_total,
        "chunks": chunk_total,
        "pages": page_total,
        "by_source_type": [
            {"type": r["source_type"], "documents": r["c"]} for r in by_source
        ],
        "by_top_category": [
            {"category": r["category"], "documents": r["c"]} for r in by_topcat
        ],
        "by_category": [
            {
                "category": r["content_type"] or "uncategorized",
                "label": _CATEGORY_LABELS.get(r["content_type"], "Uncategorized"),
                "chunks": r["c"],
            }
            for r in by_category
        ],
        "size": {
            "pdf_bytes": pdf_bytes,
            "zim_bytes": zim_bytes,
            "web_bytes": web_bytes,
            "sources_bytes": pdf_bytes + zim_bytes + web_bytes,
            "database_bytes": db_bytes,
            "vector_bytes": vector_bytes,
            "total_bytes": pdf_bytes + zim_bytes + web_bytes + db_bytes + vector_bytes,
        },
    }

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    return FileResponse(INDEX_HTML)

@app.post("/ingest/start")
async def ingest_start(
    files: list[UploadFile] = File(default=[]),
    urls: str = Form(default=""),
    web_link_pattern: str = Form(default=""),
    download_pdfs: bool = Form(default=False),
):
    """Save uploaded PDFs + queue source URLs, then run the ingestion pipeline
    in the background. URLs are routed by type behind the scenes (.zim archives
    are downloaded; everything else is crawled as a web index). Returns a
    job_id to stream progress from."""
    all_urls = [u.strip() for u in urls.splitlines() if u.strip()]
    zim_list: list[str] = []
    web_list: list[str] = []
    for url in all_urls:
        if not re.match(r"^https?://", url, re.IGNORECASE):
            return JSONResponse({"error": f"Not an http(s) URL: {url}"}, status_code=400)
        if url.lower().split("?", 1)[0].endswith(".zim"):
            zim_list.append(url)
        else:
            web_list.append(url)

    link_pattern = web_link_pattern.strip() or None
    if link_pattern:
        try:
            re.compile(link_pattern)
        except re.error as exc:
            return JSONResponse({"error": f"Invalid link pattern regex: {exc}"}, status_code=400)

    saved_pdfs: list[str] = []
    config.PDF_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for upload in files:
        name = Path(upload.filename or "").name
        if not name.lower().endswith(".pdf"):
            continue
        dest = (config.PDF_SOURCE_DIR / name).resolve()
        if config.PDF_SOURCE_DIR.resolve() not in dest.parents:
            continue
        dest.write_bytes(await upload.read())
        saved_pdfs.append(name)

    if not saved_pdfs and not all_urls:
        return JSONResponse(
            {"error": "No PDF files or URLs provided"}, status_code=400
        )

    job_id = start_ingest_job(saved_pdfs, zim_list, web_list, link_pattern, download_pdfs)
    return {"job_id": job_id}

@app.post("/ingest/preview")
def ingest_preview(
    urls: str = Form(default=""),
    web_link_pattern: str = Form(default=""),
):
    """Estimate what the given URLs would add before a full ingest run: web
    index pages report an estimated page count + disk size; .zim archives
    report their download size."""
    all_urls = [u.strip() for u in urls.splitlines() if u.strip()]
    for url in all_urls:
        if not re.match(r"^https?://", url, re.IGNORECASE):
            return JSONResponse({"error": f"Not an http(s) URL: {url}"}, status_code=400)
    if not all_urls:
        return JSONResponse({"error": "No URLs provided"}, status_code=400)

    pattern = web_link_pattern.strip() or None
    if pattern:
        try:
            re.compile(pattern)
        except re.error as exc:
            return JSONResponse({"error": f"Invalid link pattern regex: {exc}"}, status_code=400)

    from ingestion.web_reader import preview_web_index, probe_download_size

    previews = []
    for url in all_urls:
        try:
            if url.lower().split("?", 1)[0].endswith(".zim"):
                previews.append({
                    "url": url,
                    "kind": "zim",
                    "pages": 0,
                    "sampled": 0,
                    "avg_article_bytes": 0,
                    "estimated_bytes": probe_download_size(url),
                })
            else:
                previews.append(preview_web_index(url, pattern))
        except Exception as exc:
            return JSONResponse(
                {"error": f"Could not preview {url}: {exc}"}, status_code=400
            )

    return {
        "previews": previews,
        "total_pages": sum(p["pages"] for p in previews),
        "total_estimated_bytes": sum(p["estimated_bytes"] for p in previews),
    }

@app.get("/ingest/stream/{job_id}")
def ingest_stream(job_id: str):
    """NDJSON stream of stage/progress events for a running ingest job."""
    gen = stream_job(job_id)
    if gen is None:
        return JSONResponse({"error": "Unknown or finished job"}, status_code=404)
    return StreamingResponse(
        gen,
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/pdf/{filename}")
def serve_pdf(filename: str):
    """Serve a single PDF inline (opens in the browser's native viewer)."""
    safe_name = Path(filename).name
    root = config.PDF_SOURCE_DIR.resolve()
    pdf_path = (root / safe_name).resolve()

    if (
        root not in pdf_path.parents
        or not pdf_path.is_file()
        or pdf_path.suffix.lower() != ".pdf"
    ):
        return JSONResponse({"error": "Not found"}, status_code=404)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )

@app.get("/web/{filename}")
def serve_web_snapshot(filename: str):
    """Serve a locally-saved offline snapshot of a crawled web article."""
    safe_name = Path(filename).name
    root = config.WEB_SOURCE_DIR.resolve()
    path = (root / safe_name).resolve()

    if root not in path.parents or not path.is_file() or path.suffix.lower() != ".html":
        return JSONResponse({"error": "Not found"}, status_code=404)

    return FileResponse(path, media_type="text/html")

@app.get("/zim/{zim_file}/{article_path:path}")
def serve_zim_entry(zim_file: str, article_path: str):
    """Serve any entry (HTML/PDF/image/CSS) live from the .zim, so articles
    render with their assets. Injects a <base> so relative asset links resolve."""
    archive = _get_archive(zim_file)
    if archive is None:
        return JSONResponse({"error": "ZIM not found"}, status_code=404)

    path = unquote(article_path)
    if not archive.has_entry_by_path(path):
        return JSONResponse({"error": "Article not found"}, status_code=404)

    entry = archive.get_entry_by_path(path)
    if entry.is_redirect:
        entry = entry.get_redirect_entry()
    item = entry.get_item()
    content = bytes(item.content)
    mimetype = item.mimetype or "application/octet-stream"

    if mimetype.startswith("text/html"):
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        base = f"/zim/{quote(zim_file)}/" + (quote(parent, safe='/') + "/" if parent else "")
        html = content.decode("utf-8", errors="ignore")
        base_tag = f'<base href="{base}">'
        if re.search(r"<head[^>]*>", html, re.IGNORECASE):
            html = re.sub(r"(<head[^>]*>)", r"\1" + base_tag, html, count=1, flags=re.IGNORECASE)
        else:
            html = base_tag + html
        return HTMLResponse(html)

    # PDFs and other binaries: served with their real mimetype (PDF opens inline).
    return Response(content=content, media_type=mimetype)

# Serve everything else in app/static/ at /static/...
# Mounted AFTER the API routes so it never shadows /ask, /search, /library, etc.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
