from __future__ import annotations

import re
import time
from typing import Optional

import requests

from pq_wiki.config import ROBLOX_COOKIE

_ASSET_RE = re.compile(r"rbxassetid://(\d+)", re.I)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Encoding": "gzip, deflate",
}
if ROBLOX_COOKIE:
    _HEADERS["Cookie"] = f".ROBLOSECURITY={ROBLOX_COOKIE}"

_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(_HEADERS)
    return _SESSION


def parse_asset_id(texture_url: str) -> Optional[str]:
    if not texture_url:
        return None
    m = _ASSET_RE.search(texture_url)
    return m.group(1) if m else None


def fetch_asset_bytes(asset_id: str, retries: int = 2) -> bytes:
    url = f"https://assetdelivery.roblox.com/v1/asset/?id={asset_id}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = _session().get(url, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            last_err = e
            if attempt == retries - 1:
                try:
                    from pq_wiki.import_log import get_import_logger
                    get_import_logger().warning(
                        "Roblox asset fetch failed id=%s: %s (ROBLOX_COOKIE set=%s)",
                        asset_id, e, bool(ROBLOX_COOKIE),
                    )
                except Exception:
                    pass
            time.sleep(0.5 * (attempt + 1))
    assert last_err is not None
    raise last_err
