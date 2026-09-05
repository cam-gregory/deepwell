import functools
import threading
from urllib.parse import urlsplit

import pypac
from pypac.resolver import ProxyResolver

# PAC resolution runs a JavaScript engine (via pypac) that is NOT thread-safe.
# Calling it concurrently from many worker threads segfaults, so all JS
# evaluation is serialized under this lock and results are cached per host.
_lock = threading.Lock()
_resolver = None
_resolver_ready = False


def _get_resolver():
    """Discover the system's PAC file once (WPAD / platform proxy settings,
    e.g. macOS's System Configuration). Returns None on networks with no PAC
    configured, in which case callers should connect directly as normal."""
    global _resolver, _resolver_ready
    if not _resolver_ready:
        with _lock:
            if not _resolver_ready:
                pac = pypac.get_pac()
                _resolver = ProxyResolver(pac) if pac else None
                _resolver_ready = True
    return _resolver


@functools.lru_cache(maxsize=256)
def _resolve_for_host(scheme: str, host: str) -> str | None:
    resolver = _get_resolver()
    if resolver is None:
        return None
    # Serialize the (thread-unsafe) PAC JS evaluation; cached after the first hit.
    with _lock:
        proxy = resolver.get_proxy(f"{scheme}://{host}/")
    return None if proxy in (None, "DIRECT") else proxy


def resolve_proxy(url: str) -> str | None:
    """Resolve the proxy to use for `url` per the system PAC config, if any.
    Needed on corporate networks (e.g. Zscaler-managed VPNs) where the OS
    resolver can't reach the public internet directly and only a locally
    running PAC-configured proxy can — the same one browsers use. Returns
    None (connect directly) when there's no PAC or the PAC says DIRECT.

    Thread-safe: the proxy is the same for every request to a given host, so it
    is resolved once per host and reused (PAC JS is never run concurrently)."""
    parts = urlsplit(url)
    if not parts.hostname:
        return None
    return _resolve_for_host(parts.scheme or "https", parts.hostname)
