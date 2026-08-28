import json
import re
import sqlite3
from contextlib import contextmanager

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type   TEXT NOT NULL,
    source_file   TEXT NOT NULL,
    zim_file      TEXT,
    article_path  TEXT,
    title         TEXT,
    display_title TEXT,
    description   TEXT,
    page_count    INTEGER,
    open_url      TEXT,
    UNIQUE(source_file, article_path)
);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id     TEXT,
    source_type  TEXT,
    source_file  TEXT,
    title        TEXT,
    page_start   INTEGER,
    page_end     INTEGER,
    text         TEXT NOT NULL,
    keywords     TEXT,          -- JSON array
    content_type TEXT,
    difficulty   TEXT,
    zim_file     TEXT,
    article_path TEXT,
    faiss_row    INTEGER        -- position in FAISS; NULL until indexed
);

CREATE INDEX IF NOT EXISTS idx_chunks_faiss ON chunks(faiss_row);
CREATE INDEX IF NOT EXISTS idx_docs_lookup ON documents(source_file, article_path);

-- External-content FTS5 mirror of chunks.text (this IS your BM25 index).
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
USING fts5(text, content='chunks', content_rowid='id');
"""

@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db() -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)

def reset_db() -> None:
    """Drop derived tables so a rebuild starts clean."""
    with connect() as conn:
        conn.executescript(
            "DROP TABLE IF EXISTS chunks_fts;"
            "DROP TABLE IF EXISTS chunks;"
            "DROP TABLE IF EXISTS documents;"
        )
    init_db()

def fts_match_query(text: str) -> str:
    """Turn free text into a safe FTS5 MATCH string (OR of quoted tokens)."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return " OR ".join(f'"{t}"' for t in tokens)

# --- Reads used by search + library ---

def get_chunks_by_ids(conn, ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    q = f"SELECT * FROM chunks WHERE id IN ({','.join('?' * len(ids))})"
    return {row["id"]: dict(row) for row in conn.execute(q, ids)}

def faiss_row_map(conn) -> list[int]:
    """faiss position -> chunk id, ordered by faiss_row."""
    rows = conn.execute(
        "SELECT id FROM chunks WHERE faiss_row IS NOT NULL ORDER BY faiss_row"
    ).fetchall()
    return [r["id"] for r in rows]

def chunk_to_search_dict(row: dict) -> dict:
    """Shape a chunk row like the old pickled chunk dict (keeps search.py stable)."""
    return {
        "chunk_id": row.get("chunk_id"),
        "source_type": row.get("source_type"),
        "source_file": row.get("source_file"),
        "title": row.get("title"),
        "page_start": row.get("page_start"),
        "page_end": row.get("page_end"),
        "text": row.get("text"),
        "zim_file": row.get("zim_file"),
        "article_path": row.get("article_path"),
        "metadata": {
            "keywords": json.loads(row["keywords"]) if row.get("keywords") else [],
            "content_type": row.get("content_type"),
            "difficulty": row.get("difficulty"),
        },
    }
