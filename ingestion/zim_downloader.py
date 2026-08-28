from pathlib import Path
import httpx

from app import config

def download_zim(url: str, force: bool = False) -> Path:
    """Stream a .zim file from a Kiwix URL into ZIM_SOURCE_DIR.
    Writes to a .part temp file and atomically renames on success."""
    if not url.endswith(".zim"):
        raise ValueError(f"URL does not point to a .zim file: {url}")

    config.ZIM_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    dest = config.ZIM_SOURCE_DIR / filename

    if dest.exists() and not force:
        print(f"Already downloaded: {filename}")
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"Downloading {filename} ...")

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
    print(f"Saved: {dest}")
    return dest

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m ingestion.zim_downloader <kiwix-url> [<url> ...]")
        raise SystemExit(1)
    for u in sys.argv[1:]:
        download_zim(u)
