import json
from urllib.parse import quote

from app import config
from app import db
from ingestion.web_reader import slugify_url

def _open_url(doc: dict) -> str:
    if doc.get("source_type") == "zim":
        return f"/zim/{quote(doc['zim_file'])}/{quote(doc.get('article_path',''), safe='/')}"
    if doc.get("source_type") == "web":
        # Offline snapshot saved at crawl time; filename derived from the
        # URL itself so no extra DB column/join-key change is needed.
        return f"/web/{quote(slugify_url(doc['source_file']))}.html"
    return f"/pdf/{quote(doc['source_file'])}"

def load_to_db() -> None:
    """Rebuild documents + chunks + FTS from the extracted/enriched JSON on disk.
    Fast full rebuild — fine for the current corpus size."""
    db.reset_db()

    # 1. Documents from extracted/*.json (skip dotfiles).
    doc_ids: dict[tuple, int] = {}
    with db.connect() as conn:
        for path in sorted(config.EXTRACTED_DIR.glob("*.json")):
            if path.name.startswith("."):
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
            key = (doc["source_file"], doc.get("article_path"))
            cur = conn.execute(
                """INSERT OR REPLACE INTO documents
                   (source_type, source_file, zim_file, article_path,
                    title, display_title, description, page_count, open_url)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    doc.get("source_type"), doc["source_file"], doc.get("zim_file"),
                    doc.get("article_path"), doc.get("title"),
                    doc.get("display_title") or doc.get("title"),
                    doc.get("description", ""), doc.get("page_count"),
                    _open_url(doc),
                ),
            )
            doc_ids[key] = cur.lastrowid

        # 2. Chunks from enriched/*_enriched.json, linked to their document.
        n = 0
        for path in sorted(config.ENRICHED_DIR.glob("*_enriched.json")):
            for ch in json.loads(path.read_text(encoding="utf-8")):
                meta = ch.get("metadata", {})
                key = (ch["source_file"], ch.get("article_path"))
                document_id = doc_ids.get(key) or doc_ids.get((ch["source_file"], None))
                cur = conn.execute(
                    """INSERT INTO chunks
                       (document_id, chunk_id, source_type, source_file, title,
                        page_start, page_end, text, keywords, content_type,
                        difficulty, zim_file, article_path)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        document_id, ch.get("chunk_id"), ch.get("source_type"),
                        ch.get("source_file"), ch.get("title"),
                        ch.get("page_start"), ch.get("page_end"), ch["text"],
                        json.dumps(meta.get("keywords", [])),
                        meta.get("content_type"), meta.get("difficulty"),
                        ch.get("zim_file"), ch.get("article_path"),
                    ),
                )
                conn.execute(
                    "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                    (cur.lastrowid, ch["text"]),
                )
                n += 1

    print(f"Loaded {len(doc_ids)} documents and {n} chunks into {config.DB_PATH}")

if __name__ == "__main__":
    load_to_db()
