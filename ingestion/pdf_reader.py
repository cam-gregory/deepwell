from pathlib import Path
import hashlib
import json

import fitz

SOURCE_DIR = Path("data/sources/pdf")
OUTPUT_DIR = Path("data/extracted")
MANIFEST_PATH = OUTPUT_DIR / ".manifest.json"

def file_hash(path: Path) -> str:
    """SHA-256 of the file's raw bytes, streamed so large PDFs don't load fully."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()

def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

def extract_pdf(pdf_path: Path) -> dict:
    document = fitz.open(pdf_path)

    pages = []
    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text").strip()
        if not text:
            continue
        pages.append(
            {
                "page_number": page_number,
                "text": text,
            }
        )

    page_count = len(document)
    document.close()

    return {                          # <-- OUTSIDE the loop (bug fix)
        "source_type": "pdf",
        "source_file": pdf_path.name,
        "title": pdf_path.stem,
        "page_count": page_count,
        "pages": pages,
    }

def save_document(document: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(document, file, ensure_ascii=False, indent=2)

def ingest_all_pdfs(force: bool = False) -> None:
    pdf_files = list(SOURCE_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDFs found in {SOURCE_DIR}")
        return

    manifest = {} if force else load_manifest()
    processed = skipped = 0

    for pdf_path in pdf_files:
        digest = file_hash(pdf_path)
        output_path = OUTPUT_DIR / f"{pdf_path.stem}.json"

        # Skip only if hash matches AND the extracted output still exists.
        if (
            not force
            and manifest.get(pdf_path.name) == digest
            and output_path.exists()
        ):
            print(f"Skipping (unchanged): {pdf_path.name}")
            skipped += 1
            continue

        print(f"Reading: {pdf_path.name}")
        document = extract_pdf(pdf_path)

        if not document["pages"]:
            print(f"  Skipped (no extractable text): {pdf_path.name}")
            continue

        save_document(document, output_path)
        manifest[pdf_path.name] = digest
        processed += 1
        print(f"  Saved: {output_path} "
              f"({document['page_count']} pages, {len(document['pages'])} with text)")

    save_manifest(manifest)
    print(f"Extraction: {processed} processed, {skipped} skipped.")

if __name__ == "__main__":
    ingest_all_pdfs()
