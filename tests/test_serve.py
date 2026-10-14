"""api/serve.py: one process serves the exported screens at / and the API at /api; the lifespan runs once, on the outer app."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.startup as startup
from api.serve import NOT_BUILT, create_app
from db.backup import backups_dir_for, list_backups

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "frontend" / "app"
REAL_OUT = ROOT / "frontend" / "out"


def page_routes() -> list[str]:
    """Every screen of the frontend, from its app/ folder: "/" and "/orders/view/" style routes."""
    routes = []
    for page in sorted(APP_DIR.rglob("page.tsx")):
        rel = page.parent.relative_to(APP_DIR).as_posix()
        routes.append("/" if rel == "." else f"/{rel}/")
    return routes


def fake_export(folder: Path) -> Path:
    """A folder shaped like `next build` output with trailingSlash: <route>/index.html for every page, 404.html, assets."""
    for route in page_routes():
        target = folder / "index.html" if route == "/" else folder / route.strip("/") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"<html><title>page {route}</title></html>", encoding="utf-8")
    (folder / "404.html").write_text("<html><title>not found page</title></html>", encoding="utf-8")
    (folder / "_next" / "static").mkdir(parents=True)
    (folder / "_next" / "static" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return folder


@pytest.fixture
def served(tmp_path):
    return create_app(fake_export(tmp_path / "out"))


def test_the_page_list_covers_the_known_screens():
    routes = page_routes()
    assert {"/", "/orders/", "/orders/view/", "/stocktake/", "/settings/"} <= set(routes)
    assert len(routes) >= 17


def test_every_screen_opens_directly_and_after_a_refresh(served):
    with TestClient(served) as client:
        for route in page_routes():
            first = client.get(route)
            again = client.get(route)  # a refresh is the same request
            assert first.status_code == again.status_code == 200, route
            assert f"page {route}" in first.text and first.text == again.text
            assert first.headers["content-type"].startswith("text/html")


def test_a_screen_without_its_trailing_slash_reaches_the_exported_page(served):
    with TestClient(served) as client:
        response = client.get("/orders", follow_redirects=False)
        assert response.status_code in (301, 302, 307, 308) and response.headers["location"].endswith("/orders/")
        assert "page /orders/" in client.get("/orders").text


def test_the_detail_page_takes_its_id_from_the_query_string(served):
    with TestClient(served) as client:
        response = client.get("/orders/view/?id=7")
        assert response.status_code == 200 and "page /orders/view/" in response.text


def test_an_unknown_page_gets_the_exported_404_page(served):
    with TestClient(served) as client:
        response = client.get("/no-such-screen/")
        assert response.status_code == 404 and "not found page" in response.text


def test_static_assets_are_served(served):
    with TestClient(served) as client:
        assert client.get("/_next/static/app.js").status_code == 200


def test_the_api_lives_under_api_and_is_never_shadowed_by_a_page(served):
    with TestClient(served) as client:
        assert client.get("/api/health").json() == {"status": "ok", "db": "ok"}
        orders = client.get("/api/orders")
        assert orders.status_code == 200 and orders.headers["content-type"].startswith("application/json")
        assert client.get("/orders/").text.startswith("<html>")  # the page, not the API
        assert client.get("/api/suppliers").json() == []
        assert client.post("/api/suppliers", json={"name": "Fictional Supply"}).status_code == 201
        assert client.get("/api/openapi.json").status_code == 200 and client.get("/api/docs").status_code == 200
        missing = client.get("/api/no-such-route")
        assert missing.status_code == 404 and missing.headers["content-type"].startswith("application/json")


def test_the_root_has_no_docs_of_its_own(served):
    with TestClient(served) as client:
        response = client.get("/docs/")
        assert response.status_code == 404 and "not found page" in response.text


def test_the_service_lifespan_runs_exactly_once_on_the_outer_app(tmp_path, monkeypatch):
    calls = []
    real = startup.init_db

    def counting(path, *args, **kwargs):
        calls.append(path)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(startup, "init_db", counting)
    served = create_app(fake_export(tmp_path / "out"))
    with TestClient(served) as client:
        assert client.get("/api/health").status_code == 200
        assert len(calls) == 1
        assert len(list_backups(backups_dir_for(calls[0]))) == 1  # one daily backup, made once
    assert len(calls) == 1


def test_without_built_screens_the_server_still_runs_and_says_what_to_do(tmp_path):
    served = create_app(tmp_path / "missing")
    with TestClient(served) as client:
        response = client.get("/")
        assert response.status_code == 200 and response.text == NOT_BUILT and "not built yet" in response.text
        assert client.get("/api/health").status_code == 200


@pytest.mark.skipif(not (REAL_OUT / "index.html").is_file(), reason="frontend/out is not built here")
def test_every_page_of_the_real_export_is_served():
    with TestClient(create_app(REAL_OUT)) as client:
        for route in page_routes():
            response = client.get(route)
            assert response.status_code == 200, route
            assert "<html" in response.text.lower()
        assert client.get("/no-such-screen/").status_code == 404
        assert (REAL_OUT / "404.html").is_file()


def test_frontend_out_is_not_committed():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    assert "frontend/out/" in ignored
