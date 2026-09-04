import json
import re

from app import config
from app.model import generate_ingest

PROMPT_CHAR_LIMIT = 2000

SYSTEM = "You write concise catalog metadata for documents. Respond with JSON only."

def friendly_title(stem: str) -> str:
    """Deterministic human-friendly title from a filename stem (fallback)."""
    cleaned = re.sub(r"[_\-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title()

def _sample_text(document: dict, limit: int = PROMPT_CHAR_LIMIT) -> str:
    parts, total = [], 0
    for page in document.get("pages", []):
        text = page.get("text", "")
        parts.append(text)
        total += len(text)
        if total >= limit:
            break
    return "\n".join(parts)[:limit]

def _extract_json(text: str) -> str:
    """Grab the first {...} block in case the model adds stray prose."""
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text

def generate_metadata(document: dict) -> dict:
    fallback = friendly_title(document.get("title", "Untitled"))
    sample = _sample_text(document)
    if not sample.strip():
        return {"display_title": fallback, "description": ""}

    prompt = f"""From the document text below, produce catalog metadata.

Return ONLY a JSON object with exactly these keys:
- "display_title": a short human-friendly title (max ~8 words), no file extension.
- "description": one or two plain sentences (max ~40 words) describing what the document covers.

DOCUMENT TEXT:
{sample}
"""

    try:
        raw = generate_ingest(prompt, SYSTEM)
        data = json.loads(_extract_json(raw))
        title = str(data.get("display_title") or "").strip() or fallback
        desc = str(data.get("description") or "").strip()
        return {"display_title": title, "description": desc}
    except Exception as exc:
        print(f"  metadata generation failed ({exc}); using fallback title")
        return {"display_title": fallback, "description": ""}

def describe_all(force: bool = False) -> None:
    """Add display_title + description to each extracted document JSON.
    Idempotent: skips docs that already have metadata unless force=True."""
    files = [
        p for p in config.EXTRACTED_DIR.glob("*.json")
        if not p.name.startswith(".")
    ]
    if not files:
        print(f"No extracted documents in {config.EXTRACTED_DIR}")
        return

    for path in files:
        with path.open("r", encoding="utf-8") as f:
            document = json.load(f)

        if not force and document.get("display_title") and "description" in document:
            print(f"Skipping (has metadata): {path.name}")
            continue

        print(f"Describing: {document.get('source_file', path.name)}")
        meta = generate_metadata(document)
        document["display_title"] = meta["display_title"]
        document["description"] = meta["description"]

        with path.open("w", encoding="utf-8") as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
        print(f"  -> {meta['display_title']}")

if __name__ == "__main__":
    import sys
    describe_all(force="--force" in sys.argv)
