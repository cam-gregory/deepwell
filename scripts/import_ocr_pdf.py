"""Import externally-OCR'd PDFs (e.g. OpenStax math/science books) into the corpus.

Deepwell's built-in PDF reader only extracts a PDF's text layer, so books whose
equations are rendered as vector art (OpenStax "web" builds) come through with
the math missing. The fix is to OCR those PDFs *outside* this repo with a
math-aware tool (marker, Nougat, Mathpix, ...) and hand the resulting text to
this script, which writes the pipeline's extracted-JSON so the rest of ingestion
(chunk -> enrich -> load -> categorize -> index) runs unchanged.

Run from the project root, in the Deepwell venv:

    # one Markdown/text file for the whole book:
    python scripts/import_ocr_pdf.py data/sources/pdf/calculus-volume-1_-_WEB.pdf calc1.md

    # OR a folder of per-page files (0001.txt, 0002.txt, ...) for real page
    # numbers in citations:
    python scripts/import_ocr_pdf.py data/sources/pdf/calculus-volume-1_-_WEB.pdf pages_dir/ --pages

Keep the PDF itself in data/sources/pdf/ so the Library "open PDF" link works;
this script also records it in the extractor manifest so the built-in pdf_reader
skips it and never overwrites the OCR'd JSON. After importing all books, run:

    python -m ingestion.chunker
    python -m ingestion.enricher
    python -m ingestion.db_loader
    python -m ingestion.categorizer
    python -m ingestion.vector_index
"""

import argparse
import hashlib
import json
from pathlib import Path

import fitz

EXTRACTED_DIR = Path("data/extracted")
MANIFEST_PATH = EXTRACTED_DIR / ".manifest.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _pages_from_dir(text_dir: Path) -> list[dict]:
    """One extracted page per file, ordered by filename (e.g. 0001.txt)."""
    pages = []
    for i, fp in enumerate(sorted(text_dir.glob("*")), start=1):
        if fp.is_file():
            text = fp.read_text(encoding="utf-8").strip()
            if text:
                pages.append({"page_number": i, "text": text})
    return pages


def import_pdf(pdf_path: Path, text_path: Path, per_page: bool) -> None:
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    if per_page:
        pages = _pages_from_dir(text_path)
    else:
        pages = [{"page_number": 1, "text": text_path.read_text(encoding="utf-8").strip()}]

    if not pages or not any(p["text"] for p in pages):
        raise SystemExit(f"No text found in {text_path}")

    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count

    document = {
        "source_type": "pdf",
        "source_file": pdf_path.name,  # must match the file in data/sources/pdf/
        "title": pdf_path.stem,
        "page_count": page_count,
        "pages": pages,
    }

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXTRACTED_DIR / f"{pdf_path.stem}.json"
    out_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    # Record the file in the extractor manifest so pdf_reader treats it as
    # already processed and won't clobber this JSON with a text-only re-extract.
    manifest = {}
    if MANIFEST_PATH.exists():
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            manifest = {}
    manifest[pdf_path.name] = _sha256(pdf_path)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    total_chars = sum(len(p["text"]) for p in pages)
    print(f"Wrote {out_path.name}: {len(pages)} page(s), {total_chars:,} chars. "
          f"Manifest updated so pdf_reader will skip {pdf_path.name}.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Import an externally-OCR'd PDF into the corpus.")
    ap.add_argument("pdf", type=Path, help="Path to the PDF (should live in data/sources/pdf/).")
    ap.add_argument("text", type=Path, help="OCR output: a Markdown/text file, or a folder with --pages.")
    ap.add_argument("--pages", action="store_true",
                    help="Treat 'text' as a folder of per-page files (sorted) for real page numbers.")
    args = ap.parse_args()
    import_pdf(args.pdf, args.text, args.pages)


if __name__ == "__main__":
    main()
