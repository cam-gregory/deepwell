import functools

import pypac
from pypac.resolver import ProxyResolver

@functools.lru_cache(maxsize=1)
def _get_resolver():
    """Discover the system's PAC file once (WPAD / platform proxy settings,
    e.g. macOS's System Configuration). Returns None on networks with no PAC
    configured, in which case callers should connect directly as normal."""
    pac = pypac.get_pac()
    return ProxyResolver(pac) if pac else None

def resolve_proxy(url: str) -> str | None:
    """Resolve the proxy to use for `url` per the system PAC config, if any.
    Needed on corporate networks (e.g. Zscaler-managed VPNs) where the OS
    resolver can't reach the public internet directly and only a locally
    running PAC-configured proxy can — the same one browsers use. Returns
    None (connect directly) when there's no PAC or the PAC says DIRECT."""
    resolver = _get_resolver()
    if resolver is None:
        return None
    proxy = resolver.get_proxy(url)
    return None if proxy in (None, "DIRECT") else proxy
