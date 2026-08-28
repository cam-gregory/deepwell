from ingestion.zim_downloader import download_zim
from ingestion.pdf_reader import ingest_all_pdfs
from ingestion.zim_reader import ingest_all_zims
from ingestion.metadata import describe_all
from ingestion.chunker import chunk_all_documents
from ingestion.enricher import enrich_all
from ingestion.vector_index import build_index

# Curated ZIMs to fetch before ingest. Add/remove Kiwix URLs here.
ZIM_URLS: list[str] = [
    # "https://download.kiwix.org/zim/zimgit/zimgit-medicine_en_2024-08.zim",
]

def run_pipeline():
    print("\n=== 0. Downloading ZIMs ===")
    for url in ZIM_URLS:
        download_zim(url)

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

    print("\n=== 4. Building vector index ===")
    build_index()

    print("\n=== Pipeline complete ===")

if __name__ == "__main__":
    run_pipeline()
