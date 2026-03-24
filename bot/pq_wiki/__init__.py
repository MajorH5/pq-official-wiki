"""Pixel Quest wiki import bot (MediaWiki + pywikibot)."""

import os

# pywikibot loads user-config.py on first import; path must be set before that.
_bot_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PYWIKIBOT_DIR", _bot_root)

__version__ = "0.1.0"
