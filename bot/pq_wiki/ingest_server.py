from __future__ import annotations

import hmac
import json
import os
import tempfile
import threading
import traceback
from pathlib import Path

from flask import Flask, request

from pq_wiki.config import DATADUMP_INGEST_SECRET, INGEST_HOST, INGEST_PORT
from pq_wiki.import_log import get_import_logger
from pq_wiki.import_runner import run_import

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

    def _run():
        log = get_import_logger()
        try:
            out = run_import(path, force=force)
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


def main():
    app.run(host=INGEST_HOST, port=INGEST_PORT, threaded=True)


if __name__ == "__main__":
    main()
