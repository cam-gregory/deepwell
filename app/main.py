import re
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import FastAPI, Query, Response
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app import db
from app.search import search, search_debug
from app.answer import answer_question_stream

app = FastAPI(
    title="Deepwell",
    version="0.1.0",
)

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
    return FileResponse(STATIC_DIR / "debug.html")

@app.get("/ask")
def ask(
    q: str = Query(..., min_length=1, description="Question to answer"),
    limit: int = Query(5, ge=1, le=20),
):
    return StreamingResponse(
        answer_question_stream(q, limit),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/library", response_class=HTMLResponse)
def library_page():
    return FileResponse(STATIC_DIR / "library.html")

@app.get("/library/list")
def library_list(
    q: str = Query(""),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    """PDFs (one card each) + ZIM articles (one card each) from the documents table."""
    where, params = "", []
    if q:
        where = "WHERE display_title LIKE ? OR description LIKE ?"
        params = [f"%{q}%", f"%{q}%"]

    with db.connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM documents {where}", params
        ).fetchone()["c"]
        rows = conn.execute(
            f"""SELECT source_type, source_file, display_title, description,
                       page_count, open_url
                FROM documents {where}
                ORDER BY display_title
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
