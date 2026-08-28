import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app import config
from app import db

def build_index() -> None:
    with db.connect() as conn:
        rows = conn.execute("SELECT id, text FROM chunks ORDER BY id").fetchall()

    if not rows:
        print("No chunks in DB; run load_to_db first.")
        return

    ids = [r["id"] for r in rows]
    texts = [r["text"] for r in rows]
    print(f"Loaded {len(texts)} chunks from DB")

    model = SentenceTransformer(config.EMBEDDING_MODEL)
    print("Creating embeddings...")
    embeddings = model.encode(
        texts, batch_size=32, show_progress_bar=True,
        normalize_embeddings=True, convert_to_numpy=True,
    )
    embeddings = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    config.VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(config.VECTOR_DIR / "knowledge.index"))

    # Record faiss position -> chunk id mapping back into the DB.
    with db.connect() as conn:
        conn.executemany(
            "UPDATE chunks SET faiss_row = ? WHERE id = ?",
            [(pos, cid) for pos, cid in enumerate(ids)],
        )

    print(f"Indexed {len(texts)} chunks · dim {embeddings.shape[1]}")

if __name__ == "__main__":
    build_index()
