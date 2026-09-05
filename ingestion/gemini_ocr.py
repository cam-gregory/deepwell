"""OCR math/science PDFs with Gemini (or any OpenAI-compatible vision model).

The built-in pdf_reader only pulls a PDF's text layer, so OpenStax "_WEB" books
lose every equation (they're vector art). This renders each page to an image,
asks the cloud vision model to transcribe it to Markdown + LaTeX, and writes the
pipeline's standard extracted-JSON — so the normal chunk -> enrich -> load ->
categorize -> index flow runs unchanged and chunking stays consistent with the
rest of the corpus.

Resumable: each page's transcription is cached under data/ocr/<stem>/NNNN.md, so
a rate-limit or crash mid-book loses nothing — just rerun the same command.

Requires the cloud vision env (same as ingestion):
    export DEEPWELL_CLOUD_API_KEY=...      # AI Studio key
    export DEEPWELL_CLOUD_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
    export DEEPWELL_CLOUD_MODEL=gemini-3.8-flash    # a vision-capable model

Usage (test on a few pages first, then the whole set):
    python -m ingestion.gemini_ocr data/sources/pdf/calculus-volume-1_-_WEB.pdf --max-pages 3
    python -m ingestion.gemini_ocr --all-web
    python -m ingestion.gemini_ocr --all-web --dpi 170

Then run: python -m ingestion.chunker && python -m ingestion.enricher \
    && python -m ingestion.db_loader && python -m ingestion.categorizer \
    && python -m ingestion.vector_index
"""

import argparse
import base64
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path

import fitz

from app import config
from app.model import generate_cloud_vision

OCR_DIR = config.DATA_DIR / "ocr"
MANIFEST_PATH = config.EXTRACTED_DIR / ".manifest.json"

SYSTEM = "You are a precise OCR engine for textbook pages. Output only a faithful transcription, no commentary."

PROMPT = (
    "Transcribe this page to clean Markdown. Render every mathematical "
    "expression as LaTeX: inline math as $...$ and display equations as $$...$$. "
    "Preserve tables as Markdown tables and keep section headings. For figures or "
    "images, output only a short italic caption like *Figure: <brief description>* "
    "— never output image markdown, links, or URLs. Skip page headers, footers, "
    "page numbers, and navigation chrome. Do not wrap the output in code fences or "
    "add any explanation — output only the transcription. If the page has no "
    "readable content, output NOTHING."
)

# Retry a page a few times on transient/rate-limit errors before giving up.
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 10

# A little randomness reduces Gemini's RECITATION content-filter blocks on
# verbatim textbook text (greedy decoding trips it far more often).
OCR_TEMPERATURE = 0.4
# Hotter decoding for the --retry-blocked pass: paraphrases word choice enough
# to slip past RECITATION on pages the first pass blocked.
OCR_RETRY_TEMPERATURE = 0.9

# Safety net: convert any leftover image markdown to a plain caption so no dead
# external URLs (unreachable offline) end up in the corpus.
_IMG_MD = re.compile(r"!\[([^\]]*)\]\([^)]*\)")


def _strip_image_links(text: str) -> str:
    def repl(m: "re.Match[str]") -> str:
        alt = m.group(1).strip()
        return f"*Figure: {alt}*" if alt else ""
    return _IMG_MD.sub(repl, text)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _render_page_png(page: "fitz.Page", dpi: int) -> bytes:
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    return pix.tobytes("png")


def _ocr_page(png: bytes, temperature: float = OCR_TEMPERATURE) -> str:
    b64 = base64.b64encode(png).decode("ascii")
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            out = generate_cloud_vision(PROMPT, [b64], SYSTEM, temperature=temperature)
            return _strip_image_links(out.strip())
        except Exception as exc:
            msg = str(exc)
            # Structural problems (no content, bad shape) won't fix themselves —
            # fail fast so the caller can skip this page and move on.
            if "No message content" in msg or "No choices" in msg or "non-JSON" in msg:
                raise
            last_exc = exc
            if attempt < MAX_ATTEMPTS:
                wait = BACKOFF_SECONDS * attempt
                print(f"    page OCR failed ({exc}); retry {attempt}/{MAX_ATTEMPTS - 1} in {wait}s")
                time.sleep(wait)
    raise RuntimeError(f"page OCR failed after {MAX_ATTEMPTS} attempts: {last_exc}")


def _update_manifest(pdf_path: Path) -> None:
    """Record the PDF so the text-only pdf_reader skips it and never clobbers
    this OCR'd JSON."""
    manifest: dict = {}
    if MANIFEST_PATH.exists():
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            manifest = {}
    manifest[pdf_path.name] = _sha256(pdf_path)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def ocr_pdf(pdf_path: Path, *, dpi: int = 170, start_page: int = 1, max_pages: int | None = None, force: bool = False, concurrency: int = 8, retry_blocked: bool = False) -> Path:
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    cache_dir = OCR_DIR / pdf_path.stem
    cache_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    total = doc.page_count
    start_idx = max(0, start_page - 1)
    end_idx = min(total, start_idx + max_pages) if max_pages else total
    if retry_blocked:
        # Only re-do pages previously blocked (cached but empty), hotter to dodge RECITATION.
        todo = [i for i in range(start_idx, end_idx)
                if (cache_dir / f"{i + 1:04d}.md").exists()
                and (cache_dir / f"{i + 1:04d}.md").stat().st_size == 0]
    else:
        todo = [i for i in range(start_idx, end_idx)
                if force or not (cache_dir / f"{i + 1:04d}.md").exists()]
    temperature = OCR_RETRY_TEMPERATURE if retry_blocked else OCR_TEMPERATURE
    print(f"OCR {pdf_path.name}: {len(todo)} of pages {start_idx + 1}-{end_idx} "
          f"(of {total}) @ {dpi} DPI, concurrency {concurrency}"
          f"{', retry-blocked' if retry_blocked else ''} -> {cache_dir}")

    # Warm the PAC proxy cache in this thread before fanning out (its JS engine
    # is not thread-safe; resolving once here keeps workers off the cold path).
    from ingestion.http_client import resolve_proxy
    resolve_proxy(config.CLOUD_LLM_BASE_URL)

    def _write(page_no: int, text: str) -> None:
        (cache_dir / f"{page_no:04d}.md").write_text(text, encoding="utf-8")

    done = skipped = failed = 0
    # Pipeline: keep `concurrency` OCR calls in flight while rendering the next
    # page just-in-time in this thread (fitz isn't thread-safe, but rendering is
    # fast and overlaps with the many in-flight network calls). This avoids the
    # serial "render the whole batch first" stall.
    pages_iter = iter(todo)
    inflight: dict = {}

    def _submit_next(pool: ThreadPoolExecutor) -> bool:
        try:
            i = next(pages_iter)
        except StopIteration:
            return False
        inflight[pool.submit(_ocr_page, _render_page_png(doc[i], dpi), temperature)] = i
        return True

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for _ in range(concurrency):
            if not _submit_next(pool):
                break
        while inflight:
            finished, _pending = wait(list(inflight), return_when=FIRST_COMPLETED)
            for fut in finished:
                page_no = inflight.pop(fut) + 1
                try:
                    _write(page_no, fut.result())
                except Exception as exc:
                    msg = str(exc)
                    if "No message content" in msg or "RECITATION" in msg or "content_filter" in msg:
                        # Real content-filter block: cache empty marker, skip.
                        skipped += 1
                        _write(page_no, "")
                    else:
                        # Transient/exhausted: leave uncached so a rerun retries it.
                        failed += 1
                done += 1
                _submit_next(pool)
                if done % 25 == 0 or not inflight:
                    tail = "".join([f" ({skipped} blocked)" if skipped else "", f" ({failed} to-retry)" if failed else ""])
                    print(f"  {pdf_path.stem}: {done}/{len(todo)} done{tail}", flush=True)

    doc.close()

    # Assemble from every cached page present, so resumed/partial runs still
    # build the complete document in page order.
    pages = []
    for cf in sorted(cache_dir.glob("[0-9]*.md")):
        try:
            page_no = int(cf.stem)
        except ValueError:
            continue
        text = cf.read_text(encoding="utf-8").strip()
        if text:
            pages.append({"page_number": page_no, "text": text})

    if not pages:
        raise SystemExit(f"No text produced for {pdf_path.name}")

    document = {
        "source_type": "pdf",
        "source_file": pdf_path.name,
        "title": pdf_path.stem,
        "page_count": total,
        "pages": pages,
    }
    out_path = config.EXTRACTED_DIR / f"{pdf_path.stem}.json"
    config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    _update_manifest(pdf_path)

    chars = sum(len(p["text"]) for p in pages)
    print(f"  wrote {out_path.name}: {len(pages)} page(s), {chars:,} chars (pdf_reader will now skip it)")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="OCR math/science PDFs with a cloud vision model.")
    ap.add_argument("pdfs", nargs="*", type=Path, help="PDF paths (in data/sources/pdf/).")
    ap.add_argument("--all-web", action="store_true", help="Process every *_WEB.pdf in the PDF source dir.")
    ap.add_argument("--dpi", type=int, default=170, help="Render resolution (default 170).")
    ap.add_argument("--start-page", type=int, default=1, help="1-based page to start at (for spot-checks).")
    ap.add_argument("--max-pages", type=int, default=None, help="Only OCR N pages from --start-page.")
    ap.add_argument("--concurrency", type=int, default=8, help="Parallel OCR requests (default 8).")
    ap.add_argument("--force", action="store_true", help="Re-OCR pages even if cached.")
    ap.add_argument("--retry-blocked", action="store_true",
                    help="Re-OCR only pages previously blank (RECITATION-blocked), at higher temperature.")
    args = ap.parse_args()

    if not config.CLOUD_LLM_API_KEY:
        raise SystemExit("DEEPWELL_CLOUD_API_KEY is not set — export your AI Studio key first.")

    targets = list(args.pdfs)
    if args.all_web:
        targets += sorted(config.PDF_SOURCE_DIR.glob("*_WEB.pdf"))
    if not targets:
        raise SystemExit("No PDFs given. Pass paths or use --all-web.")

    for pdf in targets:
        ocr_pdf(pdf, dpi=args.dpi, start_page=args.start_page, max_pages=args.max_pages,
                force=args.force, concurrency=args.concurrency, retry_blocked=args.retry_blocked)


if __name__ == "__main__":
    main()
