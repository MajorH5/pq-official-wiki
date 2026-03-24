import os
from pathlib import Path

# Working directory when running in Docker: /bot
BOT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = BOT_ROOT / "state"
CACHE_DIR = BOT_ROOT / "cache"
TEXTURE_CACHE_DIR = CACHE_DIR / "textures"
WIKI_UPLOAD_MAP_PATH = CACHE_DIR / "wiki_image_map.json"
LAST_VERSION_PATH = STATE_DIR / "last_datadump_version.json"
WIKI_OVERRIDES_PATH = BOT_ROOT / "wiki_overrides.json"

ROBLOX_COOKIE = os.environ.get("ROBLOX_COOKIE", "").strip()
WIKI_BOT_USER = os.environ.get("WIKI_BOT_USER", "Pqadmin").strip()

DATADUMP_INGEST_SECRET = os.environ.get("DATADUMP_INGEST_SECRET", "").strip()
INGEST_HOST = os.environ.get("INGEST_HOST", "0.0.0.0")
INGEST_PORT = int(os.environ.get("INGEST_PORT", "8081"))

GENERATE_FEW_PAGES = os.environ.get("GENERATE_FEW_PAGES", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
FORCE_OVERWRITE = os.environ.get("FORCE_OVERWRITE", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

PQ_DATA_PREFIX = "PQ/Data"


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    TEXTURE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
