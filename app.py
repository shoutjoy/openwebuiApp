# -*- coding: utf-8 -*-
"""Render/Gunicorn entrypoint.

Local Windows launcher development can continue to use webapp_flask/app.py.
Render starts this module with: gunicorn app:app
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = ROOT_DIR / "webapp_flask"

for path in (ROOT_DIR, WEBAPP_DIR):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

os.environ.setdefault("OPENWEBUI_LAUNCHER_DEPLOY_MODE", "1")

from webapp_flask.app import create_app  # noqa: E402


app = create_app(auto_start=False)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", "8000")))
    app.run(host=host, port=port)
