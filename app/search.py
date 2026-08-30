import faiss
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder

from app import config
from app import db

# --- Load models, index, and faiss->chunk map once at import ---
embed_model = SentenceTransformer(config.EMBEDDING_MODEL)

reranker = (
    CrossEncoder(config.RERANKER_MODEL)
    if config.RERANK_ENABLED
    else None
)

index = None
# faiss position -> chunk id (ordered by faiss_row). The pipeline writes
# faiss_row during build_index, so this stays in sync with the index.
_FAISS_TO_CHUNK: list[int] = []

def reload_index() -> None:
    """Re-read the FAISS index + faiss->chunk map from disk.
    Call after the corpus changes on disk (e.g. an ingest job rebuilds them)
    so a running server picks up new documents without restarting."""
    global index, _FAISS_TO_CHUNK
    index = faiss.read_index(str(config.VECTOR_DIR / "knowledge.index"))
    with db.connect() as conn:
        _FAISS_TO_CHUNK = db.faiss_row_map(conn)

reload_index()

def _dense_candidates(query: str, k: int) -> list[int]:
    """Return chunk ids from FAISS vector search."""
    emb = embed_model.encode(
        [query], normalize_embeddings=True, convert_to_numpy=True
    )
    emb = np.asarray(emb, dtype="float32")
    _, positions = index.search(emb, k)
    return [
        _FAISS_TO_CHUNK[p]
        for p in positions[0]
        if 0 <= p < len(_FAISS_TO_CHUNK)
    ]

def _fts_candidates(query: str, k: int) -> list[int]:
    """Return chunk ids from SQLite FTS5 (BM25) keyword search."""
    if not config.HYBRID_ENABLED:
        return []
    match = db.fts_match_query(query)
    if not match:
        return []
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? "
            "ORDER BY bm25(chunks_fts) LIMIT ?",
            (match, k),
        ).fetchall()
    return [r["rowid"] for r in rows]

def _gather_candidates(query: str, k: int) -> list[int]:
    """Union of dense + FTS candidate chunk ids (dedup, order-preserving)."""
    seen = set()
    candidates = []
    for cid in _dense_candidates(query, k) + _fts_candidates(query, k):
        if cid not in seen:
            seen.add(cid)
            candidates.append(cid)
    return candidates

def search(query: str, limit: int = config.FINAL_LIMIT) -> list[dict]:
    """Two-stage retrieval: hybrid recall (dense + FTS) -> cross-encoder rerank.

    Returns [{"score": float, "chunk": <chunk dict>}] with the same chunk shape
    the rest of the app expects (via db.chunk_to_search_dict).
    """
    if not query.strip():
        return []
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    cand_ids = _gather_candidates(query, config.RERANK_CANDIDATES)
    if not cand_ids:
        return []

    with db.connect() as conn:
        rows = db.get_chunks_by_ids(conn, cand_ids)

    ordered = [cid for cid in cand_ids if cid in rows]
    if not ordered:
        return []

    # Stage 2: rerank the candidate pool.
    if reranker is not None:
        pairs = [(query, rows[cid]["text"]) for cid in ordered]
        scores = reranker.predict(pairs)
        ranked = sorted(
            zip(scores, ordered), key=lambda x: x[0], reverse=True
        )
        selected = []
        per_doc: dict[str, int] = {}
        for score, cid in ranked:
            # ranked is sorted desc, so once we're below the floor nothing else passes.
            if float(score) < config.RERANK_SCORE_MIN:
                break
            src = rows[cid].get("source_file")
            if per_doc.get(src, 0) >= config.MAX_CHUNKS_PER_DOC:
                continue
            per_doc[src] = per_doc.get(src, 0) + 1
            selected.append((score, cid))
            if len(selected) >= limit:
                break
        return [
            {"score": float(score), "chunk": db.chunk_to_search_dict(rows[cid])}
            for score, cid in selected
        ]

    # Fallback: no reranker — return recall order, trimmed to limit.
    return [
        {"score": 0.0, "chunk": db.chunk_to_search_dict(rows[cid])}
        for cid in ordered[:limit]
    ]

def search_debug(query: str, limit: int = config.FINAL_LIMIT) -> dict:
    """Diagnostic retrieval: exposes dense rank, FTS rank, and rerank score
    for every candidate so you can see the reranker reordering the pool."""
    if not query.strip():
        return {"query": query, "candidates": [], "final_order": []}

    dense_ids = _dense_candidates(query, config.RERANK_CANDIDATES)
    fts_ids = _fts_candidates(query, config.RERANK_CANDIDATES)

    dense_rank = {cid: r + 1 for r, cid in enumerate(dense_ids)}
    fts_rank = {cid: r + 1 for r, cid in enumerate(fts_ids)}

    seen = set()
    candidate_ids = []
    for cid in dense_ids + fts_ids:
        if cid not in seen:
            seen.add(cid)
            candidate_ids.append(cid)

    if not candidate_ids:
        return {"query": query, "candidates": [], "final_order": []}

    with db.connect() as conn:
        rows = db.get_chunks_by_ids(conn, candidate_ids)

    candidate_ids = [cid for cid in candidate_ids if cid in rows]

    rerank_score = {}
    if reranker is not None:
        pairs = [(query, rows[cid]["text"]) for cid in candidate_ids]
        scores = reranker.predict(pairs)
        rerank_score = {cid: float(s) for cid, s in zip(candidate_ids, scores)}

    if rerank_score:
        final_ids = sorted(
            candidate_ids, key=lambda c: rerank_score[c], reverse=True
        )
    else:
        final_ids = candidate_ids

    def _row(cid: int) -> dict:
        chunk = rows[cid]
        text = chunk["text"] or ""
        return {
            "chunk_id": cid,
            "source_file": chunk["source_file"],
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"],
            "dense_rank": dense_rank.get(cid),
            "bm25_rank": fts_rank.get(cid),
            "rerank_score": round(rerank_score[cid], 4) if cid in rerank_score else None,
            "matched_by": (
                ("dense" if cid in dense_rank else "")
                + ("+bm25" if cid in fts_rank else "")
            ).strip("+") or "dense",
            "preview": (text[:240] + "…") if len(text) > 240 else text,
        }

    candidates = [_row(c) for c in candidate_ids]
    final_order = [
        {**_row(c), "final_rank": r + 1, "in_answer": r < limit}
        for r, c in enumerate(final_ids)
    ]

    return {
        "query": query,
        "candidate_count": len(candidate_ids),
        "limit": limit,
        "rerank_enabled": reranker is not None,
        "hybrid_enabled": config.HYBRID_ENABLED,
        "candidates": candidates,
        "final_order": final_order,
    }
