from pathlib import Path
import os

# --- Ollama / model ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b"

# --- Generation defaults ---
NUM_CTX = 8192
NUM_PREDICT = 1024
TEMPERATURE = 0.2
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
WEB_SOURCE_DIR = DATA_DIR / "sources" / "web"   # locally-rendered offline snapshots of crawled articles

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
RERANK_CANDIDATES = 50        # how many to pull before reranking
RERANK_SCORE_MIN = -6.0       # drop candidates the reranker scores below this
MAX_CHUNKS_PER_DOC = 2        # cap final chunks from any single source file
HYBRID_ENABLED = True         # combine dense (FAISS) + BM25 keyword recall
FINAL_LIMIT = 5               # default chunks passed to the model

DB_PATH = DATA_DIR / "knowledge.db"

# --- Optional shared-password auth ---
# Set DEEPWELL_PASSWORD to require an HTTP Basic password on every request
# (any username). Leave it unset/empty to run fully open, as when developing
# locally. Intended for exposing a test deployment to trusted users.
AUTH_PASSWORD = os.environ.get("DEEPWELL_PASSWORD", "").strip()

# --- Optional hybrid cloud ingestion LLM ---
# Deepwell always answers offline with the local Ollama model. The heavier,
# one-time ingestion steps (metadata/description generation) can optionally use
# a cloud LLM while the maintainer is online, then fall back to the local model
# on any failure or when offline — so /add keeps working with no connectivity.
# The query/answer path never uses these; embeddings stay local for consistency.
#   DEEPWELL_INGEST_LLM=cloud            enable cloud ingestion (default: local)
#   DEEPWELL_CLOUD_API_KEY=sk-...        key for the OpenAI-compatible endpoint
#   DEEPWELL_CLOUD_BASE_URL=...          any OpenAI-compatible /v1 base URL
#   DEEPWELL_CLOUD_MODEL=gpt-4o-mini     model name at that endpoint
INGEST_LLM_PROVIDER = os.environ.get("DEEPWELL_INGEST_LLM", "local").strip().lower()
CLOUD_LLM_BASE_URL = (
    os.environ.get("DEEPWELL_CLOUD_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
)
CLOUD_LLM_MODEL = os.environ.get("DEEPWELL_CLOUD_MODEL", "gpt-4o-mini").strip()
CLOUD_LLM_API_KEY = os.environ.get("DEEPWELL_CLOUD_API_KEY", "").strip()
CLOUD_REQUEST_TIMEOUT = 60.0
# Optional thinking control for models that support it (e.g. gemini-2.5-flash-lite):
# "none" disables thinking so the model returns actual content instead of spending
# the output budget on reasoning tokens. Empty = provider default.
CLOUD_REASONING_EFFORT = os.environ.get("DEEPWELL_CLOUD_REASONING", "").strip()
# Optional hard cap on output tokens (0 = provider default).
CLOUD_MAX_OUTPUT_TOKENS = int(os.environ.get("DEEPWELL_CLOUD_MAX_TOKENS", "0") or "0")

