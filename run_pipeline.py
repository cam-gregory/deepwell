from ingestion.zim_downloader import download_zim
from ingestion.pdf_reader import ingest_all_pdfs
from ingestion.zim_reader import ingest_all_zims
from ingestion.web_reader import ingest_web_index
from ingestion.metadata import describe_all
from ingestion.chunker import chunk_all_documents
from ingestion.enricher import enrich_all
from ingestion.db_loader import load_to_db
from ingestion.vector_index import build_index

# Curated ZIMs to fetch before ingest. Add/remove Kiwix URLs here.
ZIM_URLS: list[str] = [
    # "https://download.kiwix.org/zim/zimgit/zimgit-medicine_en_2024-08.zim",
]

# Curated web article indexes to crawl. Each entry is (index_url, link_pattern);
# link_pattern is an optional regex narrowing which same-site links are articles.
WEB_SOURCES: list[tuple[str, str | None]] = [
    # ("https://medlineplus.gov/ency/encyclopedia_A.htm", r"/ency/article/"),
]

def run_pipeline():
    print("\n=== 0. Downloading ZIMs ===")
    for url in ZIM_URLS:
        download_zim(url)

    print("\n=== 0b. Crawling web article indexes ===")
    for index_url, link_pattern in WEB_SOURCES:
        ingest_web_index(index_url, link_pattern)

    print("\n=== 1. Extracting PDFs ===")
    ingest_all_pdfs()

    print("\n=== 1b. Extracting ZIMs (per-article) ===")
    ingest_all_zims()

    print("\n=== 1c. Describing documents ===")
    describe_all()

    print("\n=== 2. Chunking documents ===")
    chunk_all_documents()

    print("\n=== 3. Enriching chunks ===")
    enrich_all()

    print("\n=== 4. Loading into SQLite ===")
    load_to_db()

    print("\n=== 5. Building vector index ===")
    build_index()

    print("\n=== Pipeline complete ===")

if __name__ == "__main__":
    run_pipeline()
