import os
from pathlib import Path

# Working directory when running in Docker: /bot
BOT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = BOT_ROOT / "state"
CACHE_DIR = BOT_ROOT / "cache"
TEXTURE_CACHE_DIR = CACHE_DIR / "textures"
WIKI_UPLOAD_MAP_PATH = CACHE_DIR / "wiki_image_map.json"
LAST_VERSION_PATH = STATE_DIR / "last_datadump_version.json"
# Incremental import: SHA-256 of last datadump on disk + render fingerprint (see import_diff.py)
LAST_IMPORT_STATE_PATH = STATE_DIR / "last_import_state.json"
# Cached copy of last successfully imported datadump (for JSON diff); ignored via bot/cache/
LAST_DATADUMP_CACHE_PATH = CACHE_DIR / "last_datadump.json"
WIKI_OVERRIDES_PATH = BOT_ROOT / "wiki_overrides.json"

ROBLOX_COOKIE = os.environ.get("ROBLOX_COOKIE", "").strip()
# Must match the wiki account the bot logs in as (case-insensitive compare in save.py).
# If .env sets WIKI_BOT_USER= empty, still default — empty string would skip every page as "human".
WIKI_BOT_USER = (os.environ.get("WIKI_BOT_USER") or "Pqadmin").strip() or "Pqadmin"

# Shared server secret: prefer DATADUMP_INGEST_SECRET; fall back to PQ_API_SECRET (same as wiki Roblox API).
DATADUMP_INGEST_SECRET = (
	os.environ.get("DATADUMP_INGEST_SECRET", "").strip()
	or os.environ.get("PQ_API_SECRET", "").strip()
)
INGEST_HOST = os.environ.get("INGEST_HOST", "0.0.0.0")
INGEST_PORT = int(os.environ.get("INGEST_PORT", "8081"))

def _parse_generate_few_pages_limit() -> int | None:
    """
    If set, import only this many items, locations, and entities (each list capped separately).
    Empty / 0 / invalid = no limit (full import).
    Legacy: true / yes still mean 3 each (old boolean \"few pages\" default).
    """
    raw = os.environ.get("GENERATE_FEW_PAGES", "").strip()
    if not raw:
        return None
    if raw.lower() in ("true", "yes"):
        return 3
    try:
        n = int(raw, 10)
    except ValueError:
        return None
    if n <= 0:
        return None
    return n


GENERATE_FEW_PAGES_LIMIT = _parse_generate_few_pages_limit()
FORCE_OVERWRITE = os.environ.get("FORCE_OVERWRITE", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

PQ_DATA_PREFIX = "PQ/Data"

# Repo: <project>/mediawiki/wiki_templates/*.wikitext — used by `python -m pq_wiki import-templates`
# Docker: mount that folder and set WIKI_LAYOUT_TEMPLATES_DIR=/mediawiki/wiki_templates (see docker-compose)
_default_layout = BOT_ROOT.parent / "mediawiki" / "wiki_templates"
WIKI_LAYOUT_TEMPLATES_DIR = Path(
    os.environ.get("WIKI_LAYOUT_TEMPLATES_DIR", "").strip() or str(_default_layout)
)


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TEXTURE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
