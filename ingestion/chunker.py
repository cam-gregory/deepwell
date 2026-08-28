import json
import re

from app import config

def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs while cleaning excessive whitespace."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = re.split(r"\n\s*\n", text)
    cleaned = []
    for paragraph in paragraphs:
        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        if paragraph:
            cleaned.append(paragraph)
    return cleaned

def chunk_document(document: dict) -> list[dict]:
    chunks = []
    current_text = []
    current_pages = []
    current_length = 0

    # Carry ZIM link fields through to chunks so retrieval can deep-link to /zim.
    link = {}
    if document.get("source_type") == "zim":
        link = {
            "zim_file": document.get("zim_file"),
            "article_path": document.get("article_path"),
        }

    def save_current_chunk() -> None:
        nonlocal current_length
        if not current_text:
            return
        chunk_number = len(chunks) + 1
        chunks.append(
            {
                "chunk_id": f"{document['title']}-{chunk_number:04d}",
                "source_type": document["source_type"],
                "source_file": document["source_file"],
                "title": document["title"],
                "page_start": min(current_pages),
                "page_end": max(current_pages),
                "text": "\n\n".join(current_text),
                **link,
            }
        )
        current_text.clear()
        current_pages.clear()
        current_length = 0

    for page in document["pages"]:
        page_number = page["page_number"]
        paragraphs = split_paragraphs(page["text"])

        for paragraph in paragraphs:
            if len(paragraph) > config.MAX_CHARS:
                save_current_chunk()
                for start in range(0, len(paragraph), config.TARGET_CHARS):
                    piece = paragraph[start:start + config.TARGET_CHARS]
                    chunks.append(
                        {
                            "chunk_id": f"{document['title']}-{len(chunks) + 1:04d}",
                            "source_type": document["source_type"],
                            "source_file": document["source_file"],
                            "title": document["title"],
                            "page_start": page_number,
                            "page_end": page_number,
                            "text": piece,
                            **link,
                        }
                    )
                continue

            additional_length = len(paragraph) + (2 if current_text else 0)
            if current_text and current_length + additional_length > config.TARGET_CHARS:
                save_current_chunk()

            current_text.append(paragraph)
            current_pages.append(page_number)
            current_length += len(paragraph)
            if len(current_text) > 1:
                current_length += 2

    save_current_chunk()
    return chunks

def process_document(json_path) -> None:
    with json_path.open("r", encoding="utf-8") as file:
        document = json.load(file)

    chunks = chunk_document(document)

    config.CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = config.CHUNKS_DIR / f"{json_path.stem}_chunks.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(chunks, file, ensure_ascii=False, indent=2)

    print(f"{json_path.name}: {len(chunks)} chunks -> {output_path}")

def chunk_all_documents() -> None:
    # Dot-guard: skip .manifest.json and any other hidden bookkeeping files,
    # which pathlib.glob('*.json') otherwise matches.
    documents = [
        p for p in config.EXTRACTED_DIR.glob("*.json")
        if not p.name.startswith(".")
    ]
    if not documents:
        print(f"No extracted documents found in {config.EXTRACTED_DIR}")
        return
    for json_path in documents:
        process_document(json_path)

if __name__ == "__main__":
    chunk_all_documents()
