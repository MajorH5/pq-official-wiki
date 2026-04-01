from __future__ import annotations

import hmac
import json
import os
import tempfile
import threading
import traceback
from pathlib import Path
from typing import Any

from flask import Flask, request

import difflib

from pq_wiki.config import DATADUMP_INGEST_SECRET, INGEST_HOST, INGEST_PORT
from pq_wiki.import_log import get_import_logger
from pq_wiki.import_runner import parse_kind_import_selection, run_import

app = Flask(__name__)
# Large pq-datadump.json files (set via env if needed)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("INGEST_MAX_BYTES", str(500 * 1024 * 1024)))


def _auth_ok() -> bool:
    secret = DATADUMP_INGEST_SECRET
    if not secret:
        return False
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        return hmac.compare_digest(token, secret)
    x = request.headers.get("X-PQ-Wiki-Token")
    if x:
        return hmac.compare_digest(x.strip(), secret)
    return False


def _parse_kinds_arg():
    raw = request.args.get("kinds", "")
    return parse_kind_import_selection(raw)


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


@app.route("/ingest", methods=["POST"])
def ingest():
    if not DATADUMP_INGEST_SECRET:
        return {"ok": False, "error": "DATADUMP_INGEST_SECRET not configured"}, 503
    if not _auth_ok():
        return {"ok": False, "error": "unauthorized"}, 401

    body = request.get_json(silent=True)
    if body is not None:
        if "datadump" in body:
            payload = body["datadump"]
        else:
            payload = body
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="pq_datadump_")
        os.close(fd)
        Path(tmp_path).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        path = Path(tmp_path)
    elif request.files.get("file"):
        f = request.files["file"]
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="pq_datadump_")
        os.close(fd)
        path = Path(tmp_path)
        f.save(path)
    else:
        return {"ok": False, "error": "expected JSON body or multipart file field 'file'"}, 400

    force = request.args.get("force") in ("1", "true", "yes")
    kind_selection = _parse_kinds_arg()

    def _run():
        log = get_import_logger()
        try:
            out = run_import(path, force=force, kind_selection=kind_selection)
            log.info("Background import result: %s", out)
        except Exception:
            log.error("Background import crashed:\n%s", traceback.format_exc())
        finally:
            if Path(tmp_path).exists():
                try:
                    Path(tmp_path).unlink()
                except OSError:
                    pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"ok": True, "status": "accepted", "message": "Import started in background"}, 202


@app.route("/preview", methods=["POST"])
def preview():
    """
    Dry-run import:
    - compute which pages would change
    - return unified diffs vs current wiki stored wikitext
    - do not perform uploads/saves (best-effort; deterministic filenames still appear)
    """
    if not DATADUMP_INGEST_SECRET:
        return {"ok": False, "error": "DATADUMP_INGEST_SECRET not configured"}, 503
    if not _auth_ok():
        return {"ok": False, "error": "unauthorized"}, 401

    body = request.get_json(silent=True)
    tmp_path: str | None = None
    if body is not None:
        payload = body.get("datadump") if isinstance(body, dict) else None
        if payload is None:
            payload = body
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="pq_datadump_")
        os.close(fd)
        Path(tmp_path).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        path = Path(tmp_path)
    elif request.files.get("file"):
        f = request.files["file"]
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="pq_datadump_")
        os.close(fd)
        path = Path(tmp_path)
        f.save(path)
    else:
        return {"ok": False, "error": "expected JSON body or multipart file field 'file'"}, 400

    force = request.args.get("force") in ("1", "true", "yes")
    kind_selection = _parse_kinds_arg()
    max_changes = int(request.args.get("max_changes", "50"))
    max_diff_chars = int(request.args.get("max_diff_chars", "50000"))

    # Patch import_runner.save_bot_page (used inside run_import closures) to compute diffs.
    from pq_wiki import import_runner as ir
    import pywikibot

    changes: list[dict[str, Any]] = []

    old_env = os.environ.get("PQ_BOT_DRY_RUN_UPLOADS")
    os.environ["PQ_BOT_DRY_RUN_UPLOADS"] = "1"

    def _norm_wikitext(s: str) -> str:
        return s.replace("\r\n", "\n").replace("\r", "\n").strip()

    def _truncate(s: str, n: int) -> str:
        if n <= 0 or len(s) <= n:
            return s
        return s[:n] + "\n...TRUNCATED..."

    orig_save_bot_page = ir.save_bot_page

    def save_bot_page_preview(
        site: pywikibot.Site,
        title: str,
        text: str,
        version: str,
        bot_user: str,
        kind: str,
        force_overwrite: bool = False,
    ) -> str:
        if 0 <= max_changes <= len(changes):
            return "changed_truncated"

        page = pywikibot.Page(site, title)
        old_text = ""
        old_len = 0
        old_rev_id = None
        if page.exists():
            try:
                page.get()
                old_text = page.text or ""
                old_len = len(old_text)
                old_rev_id = getattr(page, "latest_revision_id", None)
            except Exception:
                old_text = ""
                old_len = 0

        if _norm_wikitext(old_text) == _norm_wikitext(text):
            return "unchanged"

        diff_lines = difflib.unified_diff(
            old_text.splitlines(True),
            (text or "").splitlines(True),
            fromfile=f"{title} (old)",
            tofile=f"{title} (new)",
            n=3,
        )
        diff_text = _truncate("".join(diff_lines), max_diff_chars)

        changes.append(
            {
                "kind": kind,
                "title": title,
                "old_rev_id": old_rev_id,
                "old_len": old_len,
                "new_len": len(text or ""),
                "diff": diff_text,
            }
        )
        return "changed"

    try:
        ir.save_bot_page = save_bot_page_preview
        out = run_import(path, force=force, dry_run=True, kind_selection=kind_selection)
        return {"ok": True, "import": out, "changes": changes, "count": len(changes)}
    except Exception as e:
        get_import_logger().error("Preview crashed: %s\n%s", e, traceback.format_exc())
        return {"ok": False, "error": str(e)}, 500
    finally:
        ir.save_bot_page = orig_save_bot_page
        if old_env is None:
            os.environ.pop("PQ_BOT_DRY_RUN_UPLOADS", None)
        else:
            os.environ["PQ_BOT_DRY_RUN_UPLOADS"] = old_env
        if tmp_path and Path(tmp_path).exists():
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass


def main():
    app.run(host=INGEST_HOST, port=INGEST_PORT, threaded=True)


if __name__ == "__main__":
    main()
