from urllib.parse import urljoin, urlparse
from pathlib import Path
import hashlib
import html
import json
import re
import time

import httpx
from bs4 import BeautifulSoup

from app import config
from ingestion.http_client import resolve_proxy

MANIFEST_PATH = config.EXTRACTED_DIR / ".web_manifest.json"
USER_AGENT = "Deepwell/0.1 (personal offline knowledge base builder)"
REQUEST_DELAY = 0.3  # seconds between article fetches, be polite to the source site
MIN_ARTICLE_CHARS = 200  # shorter than this is probably nav/listing chrome, not content
MAX_LINK_DENSITY = 0.5  # above this fraction of link text, a page is an index/nav list, not an article
MAX_PDF_BYTES = 100 * 1024 * 1024  # skip a single linked PDF larger than this
# Article text is re-stored across the pipeline (extracted JSON, offline snapshot,
# chunks, enriched chunks, SQLite rows, embeddings), so a crawl's on-disk
# footprint is several times the raw article text.
DISK_ESTIMATE_MULTIPLIER = 4.0

# Common site-chrome lines (skip links, .gov/cookie banners) that sometimes
# live outside <article>/<main> and slip past the tag-based strip — a
# fallback safety net for sites without clean semantic markup.
_BOILERPLATE_LINE_RE = re.compile(
    r"^(skip (to )?(the )?(main )?(navigation|content)\b"
    r"|official website of the united states government"
    r"|a \.gov website belongs to an official"
    r"|official websites use \.gov"
    r"|share sensitive information only on official"
    r"|the \.gov means it'?s official"
    r"|before sharing sensitive information"
    r"|we use cookies\b"
    r"|accept (all )?cookies\b"
    r"|this (site|website) uses cookies"
    r"|enable javascript"
    r"|your browser does(?:n'?t| not) support)",
    re.IGNORECASE,
)

def _strip_boilerplate_lines(text: str) -> str:
    lines = [ln for ln in text.split("\n") if not _BOILERPLATE_LINE_RE.match(ln.strip())]
    return "\n".join(lines)

# MediaWiki infrastructure URLs that are never article content. Dropped during
# link extraction even when no link_pattern is given, so wiki crawls don't
# ingest edit/history/API endpoints or Special:/User:/Talk:/etc. namespace
# pages. Conservative on purpose: only matches canonical MediaWiki markers, so
# it's a no-op on non-wiki sites (plain paths have no action=/namespace colons).
_WIKI_INFRA_RE = re.compile(
    r"(/w/(index|rest|api|load)\.php"
    r"|/api\.php"
    r"|[?&]action=(edit|history|raw|info|purge|watch|delete)"
    r"|[?&](redirect=no|oldid=|veaction=)"
    r"|/(Special|Talk|User|User_talk|Category|Category_talk|Help|Help_talk"
    r"|File|File_talk|Template|Template_talk|MediaWiki|MediaWiki_talk"
    r"|Module|Portal|Draft|Media):)",
    re.IGNORECASE,
)

def _is_wiki_infra_url(url: str) -> bool:
    return bool(_WIKI_INFRA_RE.search(url))

def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {}

def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

def slugify_url(url: str) -> str:
    """Deterministic filename stem for a URL — used for both the extracted
    JSON and the offline HTML snapshot, so db_loader can derive the snapshot
    path from source_file (the URL) without any extra DB column."""
    parsed = urlparse(url)
    raw = f"{parsed.netloc}{parsed.path}"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    return slug[:120] or hashlib.sha1(url.encode()).hexdigest()[:16]

def _extract_links(html: str, base_url: str, link_pattern: str | None) -> list[str]:
    """Same-site links from a listing page, optionally narrowed by a regex
    matched against the absolute URL (e.g. r"/article/" to skip nav links)."""
    soup = BeautifulSoup(html, "html.parser")
    base_netloc = urlparse(base_url).netloc
    pattern = re.compile(link_pattern) if link_pattern else None

    seen: set[str] = set()
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).netloc != base_netloc or absolute == base_url:
            continue
        if urlparse(absolute).path.lower().endswith(".pdf"):
            continue  # PDFs are harvested by _extract_pdf_links, not crawled as articles
        if _is_wiki_infra_url(absolute):
            continue
        if pattern and not pattern.search(absolute):
            continue
        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)
    return links

def _extract_pdf_links(html: str, base_url: str) -> list[str]:
    """Same-site links that point at a PDF file (by .pdf path suffix). Kept
    separate from _extract_links so PDF harvesting ignores the article
    link_pattern (which is meant for HTML article titles, not file URLs)."""
    soup = BeautifulSoup(html, "html.parser")
    base_netloc = urlparse(base_url).netloc
    seen: set[str] = set()
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).netloc != base_netloc:
            continue
        if not urlparse(absolute).path.lower().endswith(".pdf"):
            continue
        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)
    return links

def _download_linked_pdfs(client: httpx.Client, pdf_urls: list[str]) -> int:
    """Download crawled PDF links into PDF_SOURCE_DIR so the normal PDF stage
    ingests them. Path-traversal + size guarded; skips non-PDF responses."""
    dest_dir = config.PDF_SOURCE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    root = dest_dir.resolve()
    saved = 0
    for url in pdf_urls:
        name = Path(urlparse(url).path).name or (slugify_url(url) + ".pdf")
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        dest = (dest_dir / Path(name).name).resolve()
        if root not in dest.parents or dest.exists():
            continue
        try:
            r = client.get(url)
            r.raise_for_status()
            data = r.content
        except Exception as exc:
            print(f"  PDF failed: {url} ({exc})")
            continue
        if not data.startswith(b"%PDF"):
            print(f"  Not a PDF (skipped): {url}")
            continue
        if len(data) > MAX_PDF_BYTES:
            print(f"  PDF too large (skipped): {url}")
            continue
        dest.write_bytes(data)
        saved += 1
        time.sleep(REQUEST_DELAY)
    if saved:
        print(f"Downloaded {saved} linked PDF(s) to {dest_dir}")
    return saved

def _extract_article(html: str, url: str) -> dict | None:
    """Return an extracted-document dict (same shape as pdf/zim readers), or
    None if the page looks like chrome rather than an article."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    # Prefer the semantic content container so site chrome (gov/cookie
    # banners, skip links, etc. that live outside <article>/<main> and
    # aren't caught by the tag-based strip below) never enters the text.
    content_root = soup.find("article") or soup.find("main") or soup.body or soup
    for tag in content_root(["script", "style", "nav", "header", "footer", "noscript", "head"]):
        tag.decompose()

    # An index/listing page (A-Z menus, "related topics" lists) is mostly
    # hyperlinks; a real article is mostly prose. Skip pages whose text is
    # dominated by link text so navigation pages don't pollute the corpus.
    anchor_chars = sum(len(a.get_text(strip=True)) for a in content_root.find_all("a"))
    all_chars = len(content_root.get_text(strip=True))
    if all_chars and anchor_chars / all_chars > MAX_LINK_DENSITY:
        return None

    text = content_root.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = _strip_boilerplate_lines(text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()

    if len(text) < MIN_ARTICLE_CHARS:
        return None

    return {
        "source_type": "web",
        "source_file": url,  # the article's own URL doubles as its unique id + open link
        "title": title,
        "page_count": 1,
        "pages": [{"page_number": 1, "text": f"{title}\n\n{text}"}],
    }

def _paragraphs_from_text(text: str) -> list[str]:
    """Split the stored article text back into paragraph blocks for rendering."""
    blocks = re.split(r"\n\s*\n", text.strip())
    return [" ".join(b.split()) for b in blocks if b.strip()]

def render_snapshot(title: str, text: str, source_url: str) -> str:
    """Render a clean, app-styled offline copy of a crawled article — no
    network calls at render time, just the text captured during crawling."""
    paragraphs = _paragraphs_from_text(text)
    body = "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)
    safe_title = html.escape(title)
    safe_url = html.escape(source_url)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{safe_title}</title>
<style>
  body {{ margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f6f7f9; color: #1f2937; }}
  .container {{ max-width: 720px; margin: 0 auto; padding: 48px 24px; }}
  .back {{ display: inline-block; margin-bottom: 24px; color: #6b7280; text-decoration: none; font-size: 14px; }}
  h1 {{ font-size: 28px; margin: 0 0 8px; }}
  .source {{ color: #6b7280; font-size: 13px; margin-bottom: 32px; padding-bottom: 16px; border-bottom: 1px solid #e5e7eb; }}
  .source a {{ color: #6b7280; }}
  p {{ line-height: 1.7; margin: 16px 0; }}
</style>
</head>
<body>
<div class="container">
  <a class="back" href="/library">&larr; Back to Library</a>
  <h1>{safe_title}</h1>
  <div class="source">Saved offline copy &middot; originally published at
    <a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a>
  </div>
  {body}
</div>
</body>
</html>
"""

def _save_snapshot(doc: dict, url: str) -> None:
    config.WEB_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    body_text = doc["pages"][0]["text"].split("\n\n", 1)[-1]
    html_doc = render_snapshot(doc["title"], body_text, url)
    (config.WEB_SOURCE_DIR / f"{slugify_url(url)}.html").write_text(html_doc, encoding="utf-8")

def preview_web_index(
    index_url: str,
    link_pattern: str | None = None,
    max_articles: int = 300,
    sample_size: int = 5,
) -> dict:
    """Cheaply estimate what crawling `index_url` would add WITHOUT ingesting.
    Fetches the index page to count candidate article links, then samples a
    few articles to estimate average size and extrapolate the on-disk cost.
    Sampled pages that look like nav/index lists are excluded from the average."""
    with httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
        proxy=resolve_proxy(index_url),
    ) as client:
        resp = client.get(index_url)
        resp.raise_for_status()
        links = _extract_links(resp.text, index_url, link_pattern)[:max_articles]

        sizes: list[int] = []
        for url in links[:sample_size]:
            try:
                r = client.get(url)
                r.raise_for_status()
                doc = _extract_article(r.text, url)
            except Exception:
                continue
            if doc is not None:
                sizes.append(len(doc["pages"][0]["text"].encode("utf-8")))
            time.sleep(REQUEST_DELAY)

    pages = len(links)
    avg_bytes = int(sum(sizes) / len(sizes)) if sizes else 0
    return {
        "url": index_url,
        "kind": "web",
        "pages": pages,
        "sampled": len(sizes),
        "avg_article_bytes": avg_bytes,
        "estimated_bytes": int(avg_bytes * pages * DISK_ESTIMATE_MULTIPLIER),
    }

def probe_download_size(url: str) -> int:
    """Return the Content-Length of a direct download (e.g. a .zim) via HEAD,
    or 0 if the server doesn't report it."""
    with httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
        proxy=resolve_proxy(url),
    ) as client:
        r = client.head(url)
        r.raise_for_status()
        cl = r.headers.get("content-length")
        return int(cl) if cl and cl.isdigit() else 0

def ingest_web_index(
    index_url: str,
    link_pattern: str | None = None,
    max_articles: int = 300,
    force: bool = False,
    download_pdfs: bool = False,
) -> int:
    """Fetch a listing page, follow its same-site links, and save one
    extracted JSON document per article (mirrors pdf/zim extracted output).
    Already-ingested URLs are skipped unless force=True."""
    config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {} if force else _load_manifest()

    with httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
        proxy=resolve_proxy(index_url),
    ) as client:
        resp = client.get(index_url)
        resp.raise_for_status()
        if download_pdfs:
            _download_linked_pdfs(client, _extract_pdf_links(resp.text, index_url))
        links = _extract_links(resp.text, index_url, link_pattern)[:max_articles]
        print(f"Found {len(links)} candidate article links at {index_url}")

        saved = skipped = failed = 0
        for url in links:
            output_path = config.EXTRACTED_DIR / f"web-{slugify_url(url)}.json"
            if not force and url in manifest and output_path.exists():
                skipped += 1
                continue

            try:
                r = client.get(url)
                r.raise_for_status()
                doc = _extract_article(r.text, url)
            except Exception as exc:
                print(f"  Failed: {url} ({exc})")
                failed += 1
                continue

            if doc is None:
                print(f"  Skipped (too little text): {url}")
                continue

            output_path.write_text(
                json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _save_snapshot(doc, url)
            manifest[url] = True
            saved += 1
            if saved % 10 == 0:
                print(f"  ...{saved} articles saved")
            time.sleep(REQUEST_DELAY)

    _save_manifest(manifest)
    print(f"Web ingest: {saved} saved, {skipped} skipped, {failed} failed.")
    return saved

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m ingestion.web_reader <index-url> [link-pattern-regex]")
        raise SystemExit(1)
    ingest_web_index(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
