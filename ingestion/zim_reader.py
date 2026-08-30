from pathlib import Path
import json
import re

import fitz  # PyMuPDF, already a dependency
from libzim.reader import Archive
from ingestion.metadata import generate_metadata

from app import config

# --- HTML -> text (BeautifulSoup if available, stdlib fallback) ---
try:
    from bs4 import BeautifulSoup
    def html_to_text(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "nav", "header", "footer"]):
            t.decompose()
        return _collapse(soup.get_text("\n"))
except ImportError:
    from html.parser import HTMLParser
    class _S(HTMLParser):
        def __init__(self):
            super().__init__(); self._skip = 0; self.parts = []
        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"): self._skip += 1
        def handle_endtag(self, tag):
            if tag in ("script", "style") and self._skip: self._skip -= 1
        def handle_data(self, data):
            if not self._skip: self.parts.append(data)
    def html_to_text(html: str) -> str:
        s = _S(); s.feed(html); return _collapse("\n".join(s.parts))

def _collapse(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()

def first_sentences(text: str, max_chars: int = 220, max_sentences: int = 2) -> str:
    text = " ".join(text.split())
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:max_sentences]).strip()[:max_chars]

# Skip the viewer shell / search UI pages that carry no real content.
_SHELL_PATHS = {"home", "index", "index.html", "search", "404.html"}
_SHELL_MARKERS = ("No result for this search request", "Loading…")

def _pdf_to_pages(content: bytes) -> list[dict]:
    pages = []
    doc = fitz.open(stream=content, filetype="pdf")
    for pno, page in enumerate(doc, start=1):
        t = page.get_text("text").strip()
        if t:
            pages.append({"page_number": pno, "text": t})
    doc.close()
    return pages

def zim_fingerprint(path: Path) -> str:
    st = path.stat()
    return f"{st.st_size}-{int(st.st_mtime)}"

def _load(path: Path, default):
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            pass
    return default

def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _iter_entries(archive: Archive):
    count = getattr(archive, "all_entry_count", None) or archive.entry_count
    get = getattr(archive, "get_entry_by_id", None) or archive._get_entry_by_id
    for i in range(count):
        try:
            entry = get(i)
        except Exception:
            continue
        if entry.is_redirect:
            continue
        try:
            item = entry.get_item()
        except Exception:
            continue
        yield entry, item

def _article_from_entry(entry, item):
    """Return (title, pages, kind) for a content entry, or None to skip.
    kind is "pdf" or "html" — the ZIM's own filename/title for embedded PDFs
    is often just a generic bucket name (e.g. "First Aid and Medicine (10)"),
    not the real article title, so callers use it to decide whether to defer
    to the LLM-generated display_title instead of trusting this title."""
    mimetype = (item.mimetype or "")
    path = entry.path

    if path in _SHELL_PATHS:
        return None

    if mimetype.startswith("application/pdf"):
        pages = _pdf_to_pages(bytes(item.content))
        if not pages:
            return None
        title = _clean_title(entry.title, path)
        return title, pages, "pdf"

    if mimetype.startswith("text/html"):
        text = html_to_text(bytes(item.content).decode("utf-8", errors="ignore"))
        if not text.strip() or any(m in text for m in _SHELL_MARKERS):
            return None
        title = _clean_title(entry.title, path)
        return title, [{"page_number": 1, "text": f"{title}\n\n{text}"}], "html"

    return None  # images, css, js, etc.

def ingest_all_zims(force: bool = False) -> None:
    zim_files = list(config.ZIM_SOURCE_DIR.glob("*.zim"))
    if not zim_files:
        print(f"No ZIMs found in {config.ZIM_SOURCE_DIR}")
        return

    manifest = {} if force else _load(config.ZIM_MANIFEST, {})
    catalog = [] if force else _load(config.ZIM_CATALOG, [])
    config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    for zim_path in zim_files:
        fingerprint = zim_fingerprint(zim_path)
        if not force and manifest.get(zim_path.name) == fingerprint:
            print(f"Skipping (unchanged): {zim_path.name}")
            continue

        print(f"Reading: {zim_path.name}")
        for old in config.EXTRACTED_DIR.glob(f"zim-{zim_path.stem}-*.json"):
            old.unlink()
        catalog = [c for c in catalog if c.get("zim_file") != zim_path.name]

        archive = Archive(str(zim_path))
        n = 0
        for entry, item in _iter_entries(archive):
            result = _article_from_entry(entry, item)
            if result is None:
                continue
            title, pages, kind = result
            full_text = "\n\n".join(p["text"] for p in pages)
            doc = {
                "source_type": "zim",
                "source_file": zim_path.name,
                "zim_file": zim_path.name,
                "article_path": entry.path,
                "title": title,
                "page_count": len(pages),
                "pages": pages,
            }
            if kind == "html":
                # A real HTML article's own title is trustworthy; skip the
                # LLM describe step so large ZIMs don't pay per-article cost.
                doc["display_title"] = title
                doc["description"] = first_sentences(full_text)
            # PDF-derived entries keep only the generic ZIM filename as
            # "title" — describe_all() will read the actual content and
            # generate a real display_title + description from it.
            _save(config.EXTRACTED_DIR / f"zim-{zim_path.stem}-{n:05d}.json", doc)
            catalog.append({
                "zim_file": zim_path.name,
                "path": entry.path,
                "title": title,
                "description": doc.get("description", ""),
            })
            n += 1
            if n % 25 == 0:
                print(f"  ...{n} articles")

        manifest[zim_path.name] = fingerprint
        print(f"  Extracted {n} articles from {zim_path.name}")

    _save(config.ZIM_CATALOG, catalog)
    _save(config.ZIM_MANIFEST, manifest)
    print(f"ZIM catalog: {len(catalog)} article cards total.")
    
def _clean_title(raw: str, path: str) -> str:
    t = (raw or path).rsplit("/", 1)[-1]      # drop "files/" namespace prefix
    t = re.sub(r"\.pdf$", "", t, flags=re.I)  # drop .pdf
    t = t.replace("_", " ").strip()
    return t or path                           # keep "(1)" — it marks volume/part


if __name__ == "__main__":
    import sys
    ingest_all_zims(force="--force" in sys.argv)
