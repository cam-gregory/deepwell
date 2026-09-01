import json
import threading
import time
import traceback
import uuid
from typing import Optional

import httpx

from ingestion.zim_downloader import download_zim
from ingestion.pdf_reader import ingest_all_pdfs
from ingestion.zim_reader import ingest_all_zims
from ingestion.web_reader import ingest_web_index
from ingestion.metadata import describe_all
from ingestion.chunker import chunk_all_documents
from ingestion.enricher import enrich_all
from ingestion.db_loader import load_to_db
from ingestion.categorizer import categorize_all
from ingestion.vector_index import build_index

# In-memory job registry: each job keeps its full event log + status, so a
# client can disconnect (e.g. navigate away) and reconnect later without
# losing progress or interrupting the background pipeline thread, which
# runs independently of any stream consumer.
_jobs: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_JOB_TTL_SECONDS = 60 * 60  # keep finished jobs reconnectable for an hour

_STAGES = [
    ("extract_pdf", "Extracting PDFs", ingest_all_pdfs),
    ("extract_zim", "Extracting ZIM articles", ingest_all_zims),
    ("describe", "Generating titles & descriptions", describe_all),
    ("chunk", "Chunking documents", chunk_all_documents),
    ("enrich", "Enriching chunks", enrich_all),
    ("load_db", "Loading into SQLite", load_to_db),
    ("categorize", "Categorizing documents", categorize_all),
    ("index", "Building vector index", build_index),
]

def start_ingest_job(
    pdf_names: list[str],
    zim_urls: list[str],
    web_urls: list[str],
    web_link_pattern: str | None,
    download_pdfs: bool = False,
) -> str:
    """Kick off a background ingest run; PDFs must already be saved to disk."""
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _prune_old_jobs()
        _jobs[job_id] = {"events": [], "done": False, "finished_at": None}
    threading.Thread(
        target=_run,
        args=(job_id, pdf_names, zim_urls, web_urls, web_link_pattern, download_pdfs),
        daemon=True,
    ).start()
    return job_id

def _prune_old_jobs() -> None:
    """Caller must hold _JOBS_LOCK. Drops finished jobs older than the TTL."""
    cutoff = time.time() - _JOB_TTL_SECONDS
    stale = [
        jid for jid, job in _jobs.items()
        if job["finished_at"] is not None and job["finished_at"] < cutoff
    ]
    for jid in stale:
        del _jobs[jid]

def stream_job(job_id: str) -> Optional[object]:
    """Returns a generator of NDJSON lines for the job, or None if unknown.
    Replays every event recorded so far, then polls for new ones — safe to
    call multiple times (e.g. reconnecting after navigating away) since it
    never mutates or discards the job's state."""
    if job_id not in _jobs:
        return None

    def gen():
        sent = 0
        while True:
            with _JOBS_LOCK:
                job = _jobs.get(job_id)
                if job is None:
                    return
                pending = job["events"][sent:]
                sent += len(pending)
                done = job["done"]
            for event in pending:
                yield json.dumps(event) + "\n"
            if done:
                return
            time.sleep(0.25)

    return gen()

def _emit(job_id: str, **kwargs) -> None:
    with _JOBS_LOCK:
        job = _jobs.get(job_id)
        if job is not None:
            job["events"].append(kwargs)

def _finish(job_id: str) -> None:
    with _JOBS_LOCK:
        job = _jobs.get(job_id)
        if job is not None:
            job["done"] = True
            job["finished_at"] = time.time()

def _describe_fetch_error(exc: Exception, url: str) -> str:
    """Turn a raw httpx/network exception into an actionable message."""
    if isinstance(exc, httpx.ConnectError):
        return (
            f"Could not reach {url} — check the URL for typos and confirm this "
            "machine has network/DNS access to that host."
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return f"{url} returned HTTP {exc.response.status_code}."
    if isinstance(exc, httpx.RequestError):
        return f"Request to {url} failed: {exc}"
    return f"{url}: {exc}"

def _run(
    job_id: str,
    pdf_names: list[str],
    zim_urls: list[str],
    web_urls: list[str],
    web_link_pattern: str | None,
    download_pdfs: bool = False,
) -> None:
    # Imported lazily so a slow/GPU-heavy import doesn't happen at server startup.
    from app import search as search_module

    try:
        if pdf_names:
            _emit(job_id, type="stage", name="upload",
                  label=f"Saved {len(pdf_names)} PDF file(s)", status="done")

        if zim_urls:
            _emit(job_id, type="stage", name="download",
                  label="Downloading ZIM archive(s)", status="start")
            for url in zim_urls:
                try:
                    download_zim(url)
                except Exception as exc:
                    raise RuntimeError(_describe_fetch_error(exc, url)) from exc
            _emit(job_id, type="stage", name="download",
                  label="Downloading ZIM archive(s)", status="done")

        if web_urls:
            _emit(job_id, type="stage", name="crawl_web",
                  label="Crawling web article indexes", status="start")
            for url in web_urls:
                try:
                    ingest_web_index(url, web_link_pattern, download_pdfs=download_pdfs)
                except Exception as exc:
                    raise RuntimeError(_describe_fetch_error(exc, url)) from exc
            _emit(job_id, type="stage", name="crawl_web",
                  label="Crawling web article indexes", status="done")

        for name, label, fn in _STAGES:
            _emit(job_id, type="stage", name=name, label=label, status="start")
            fn()
            _emit(job_id, type="stage", name=name, label=label, status="done")

        search_module.reload_index()
        _emit(job_id, type="done")
    except Exception as exc:
        traceback.print_exc()
        _emit(job_id, type="error", message=str(exc))
    finally:
        _finish(job_id)
