"""One-process server for daily use: the exported screens (`frontend/out/`) at `/` and the API at `/api`, on one port and one
origin (no CORS, and Node is not needed to run, only to build the screens).
The API cannot live at the root here: page and API paths share names (the page `/orders/` and the API `/orders`).
`api.main:app` stays the API at the root (tests, development); this app mounts it under `/api`.
A mounted sub-app's lifespan does not run, so the service lifespan (logging, `init_db`, the daily backup, the hourly
checker) belongs to THIS outer app and runs exactly once.
Run: `python -m uvicorn api.serve:app --host 127.0.0.1 --port 8000` (tools/run_app does it for you)."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

from api.main import app as api_app
from api.startup import service_lifespan
from db.connection import PROJECT_ROOT

# $REBEL_FRONTEND_DIR lets tests (and a custom install) point at another export folder.
FRONTEND_DIR = Path(os.environ.get("REBEL_FRONTEND_DIR") or PROJECT_ROOT / "frontend" / "out")

NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>Rebel Store Manager</title>
<body style="font-family:sans-serif;max-width:40rem;margin:3rem auto;line-height:1.7" dir="ltr">
<h1>The screens are not built yet</h1>
<p>The server is running, but <code>frontend/out</code> does not exist. Close this window and double-click
<b>start-rebel.cmd</b> (it builds the screens once; this needs Node.js), or run
<code>start-rebel.cmd --rebuild</code>. The API itself works at <a href="/api/health">/api/health</a>.</p>"""


def create_app(frontend_dir: Path | str | None = None) -> FastAPI:
    directory = Path(frontend_dir) if frontend_dir is not None else FRONTEND_DIR
    root = FastAPI(title="Rebel Store Manager", lifespan=service_lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    root.mount("/api", api_app)  # API docs are at /api/docs
    if (directory / "index.html").is_file():
        # html=True: "/orders/" -> orders/index.html, "/orders" redirects to "/orders/", an unknown page gets 404.html
        root.mount("/", StaticFiles(directory=directory, html=True), name="screens")
    else:

        @root.get("/", include_in_schema=False)
        def not_built() -> HTMLResponse:
            return HTMLResponse(NOT_BUILT)

    return root


app = create_app()
