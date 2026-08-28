from pathlib import Path

# --- Ollama / model ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b"

# --- Generation defaults ---
NUM_CTX = 8192
NUM_PREDICT = 1024
TEMPERATURE = 0.4
KEEP_ALIVE = "30m"
REQUEST_TIMEOUT = 120.0

# --- Embeddings / retrieval ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Paths ---
DATA_DIR = Path("data")
EXTRACTED_DIR = DATA_DIR / "extracted"
CHUNKS_DIR = DATA_DIR / "chunks"
ENRICHED_DIR = DATA_DIR / "enriched"
VECTOR_DIR = DATA_DIR / "vectorstore"
PDF_SOURCE_DIR = DATA_DIR / "sources" / "pdf"
ZIM_SOURCE_DIR = DATA_DIR / "sources" / "zim"  

# --- ZIM sources ---
ZIM_SOURCE_DIR = DATA_DIR / "sources" / "zim"
ZIM_CATALOG = ZIM_SOURCE_DIR / ".catalog.json"      # library index; lives OUTSIDE EXTRACTED_DIR
ZIM_MANIFEST = ZIM_SOURCE_DIR / ".manifest.json"    # skip-if-unchanged cache

# --- Chunking ---
TARGET_CHARS = 2500
MAX_CHARS = 3500

# --- Retrieval / reranking ---
RERANK_ENABLED = True
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # small, local, fast
RERANK_CANDIDATES = 30        # how many to pull before reranking
HYBRID_ENABLED = True         # combine dense (FAISS) + BM25 keyword recall
FINAL_LIMIT = 5               # default chunks passed to the model

DB_PATH = DATA_DIR / "knowledge.db"

