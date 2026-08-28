"""Fetch all Deepwell source documents listed in sources.json.

PDFs are downloaded from the project's GitHub Release; ZIMs are pulled straight
from the Kiwix mirror. Every file with a recorded sha256 is verified after
download, and the run aborts on any mismatch (no silently-corrupt corpus).

Usage (run from the project root):
    python fetch_sources.py            # download + verify everything
    python fetch_sources.py --hashes   # print sha256 of local files (to fill sources.json)
"""

import hashlib
import json
import sys
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "sources.json"

PDF_DIR = ROOT / "data" / "sources" / "pdf"
ZIM_DIR = ROOT / "data" / "sources" / "zim"

PLACEHOLDER = "PASTE_HASH"


def sha256_file(path: Path) -> str:
    """Stream the file so large ZIMs don't load fully into memory."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    """Stream to a .part temp file, then atomically rename on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    # No read timeout: source files can be large (ZIMs are hundreds of MB).
    timeout = httpx.Timeout(connect=30.0, read=None, write=None, pool=None)
    with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with tmp.open("wb") as f:
            for block in r.iter_bytes(256 * 1024):
                f.write(block)
                done += len(block)
                if total:
                    print(f"\r  {done/1e6:.1f}/{total/1e6:.1f} MB "
                          f"({done/total*100:.0f}%)", end="")
        print()
    tmp.rename(dest)


def _fetch_one(entry: dict, dest_dir: Path) -> str:
    """Return 'skipped' or 'downloaded'. Aborts the run on a checksum mismatch."""
    name = entry["name"]
    url = entry["url"]
    expected = (entry.get("sha256") or "").lower().strip()
    if expected == PLACEHOLDER.lower():
        expected = ""
    dest = dest_dir / name

    # Skip if already present and (when a hash is recorded) verified.
    if dest.exists():
        if not expected:
            print(f"  Present (no hash to verify): {name}")
            return "skipped"
        if sha256_file(dest) == expected:
            print(f"  Present & verified: {name}")
            return "skipped"
        print(f"  Hash mismatch on existing file, re-downloading: {name}")

    print(f"Downloading {name} ...")
    _download(url, dest)

    if expected:
        actual = sha256_file(dest)
        if actual != expected:
            dest.unlink(missing_ok=True)
            raise SystemExit(
                f"\nABORT: checksum mismatch for {name}\n"
                f"  expected {expected}\n  actual   {actual}\n"
                f"  (deleted the bad download)"
            )
        print(f"  Verified sha256: {name}")
    else:
        print(f"  WARNING: no sha256 recorded for {name}; skipped verification")

    return "downloaded"


def fetch_sources() -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"Manifest not found: {MANIFEST}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    downloaded = skipped = 0

    for entry in manifest.get("pdfs", []):
        result = _fetch_one(entry, PDF_DIR)
        downloaded += result == "downloaded"
        skipped += result == "skipped"

    for entry in manifest.get("zims", []):
        result = _fetch_one(entry, ZIM_DIR)
        downloaded += result == "downloaded"
        skipped += result == "skipped"

    print(f"\nSources: {downloaded} downloaded, {skipped} already present.")
    print("Next: python run_pipeline.py")


def print_hashes() -> None:
    """Compute sha256 for local source files, to fill sources.json once."""
    any_found = False
    for d in (PDF_DIR, ZIM_DIR):
        for path in sorted(d.glob("*")):
            if path.is_file() and not path.name.startswith("."):
                any_found = True
                print(f"{sha256_file(path)}  {path.name}")
    if not any_found:
        print(f"No source files found under {PDF_DIR} or {ZIM_DIR}")


if __name__ == "__main__":
    if "--hashes" in sys.argv:
        print_hashes()
    else:
        fetch_sources()
