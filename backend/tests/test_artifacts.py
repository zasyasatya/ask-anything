"""Tests: artifact registry + tool generate_image / generate_ppt."""
import asyncio

import pytest

from app import artifacts


@pytest.fixture(autouse=True)
def _clean(client):
    from app import db
    ids = [r["id"] for r in db.query_all("SELECT id FROM artifacts")]
    for i in ids:
        artifacts.delete_artifact(i, settings=client.app.settings
                                  if hasattr(client.app, "settings") else None)
    yield
    ids = [r["id"] for r in db.query_all("SELECT id FROM artifacts")]
    for i in ids:
        artifacts.delete_artifact(i)


def test_register_list_read_delete(client):
    from app.config import settings

    art = artifacts.register_artifact(
        settings=settings, kind="image", title="Poster uji",
        filename="uji.svg", mime="image/svg+xml",
        data=b"<svg xmlns='http://www.w3.org/2000/svg'/>",
        conversation_id="c1", run_id="r1", meta={"generator": "poster-v1"},
    )
    assert art["url"].startswith("/api/artifacts/")
    listed = artifacts.list_artifacts(kind="image")
    assert any(a["id"] == art["id"] for a in listed)

    found = artifacts.read_artifact(art["id"], settings=settings)
    assert found and found[1].startswith(b"<svg")

    # download endpoint publik
    r = client.get(f"/api/artifacts/{art['id']}/download")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")

    assert artifacts.delete_artifact(art["id"], settings=settings)
    assert artifacts.get_artifact(art["id"]) is None
    assert client.get(f"/api/artifacts/{art['id']}/download").status_code == 404


def test_generate_image_tool_offline_poster(client):
    """Tanpa gateway gambar → fallback poster SVG deterministik + artifact."""
    from app.config import settings
    from app.tools import ToolContext, get_tool

    tool = get_tool("generate_image")
    ctx = ToolContext(settings=settings, conversation_id="cx", run_id="rx")
    res = asyncio.run(tool.run({"prompt": "kucing astronot main gitar"}, ctx))
    assert res.ok
    art = res.data["artifact"]
    assert art["kind"] == "image" and art["url"]
    stored = artifacts.read_artifact(art["id"], settings=settings)
    svg = stored[1].decode("utf-8")
    assert svg.startswith("<svg")
    assert "poster" in art["generator"]          # jujur soal asal keluaran

    # deterministik: prompt sama → SVG sama
    svg2 = None
    from app.tools.generate_image import poster_svg
    svg2, _ = poster_svg("kucing astronot main gitar")
    assert svg.strip() == svg2.strip()

    # prompt kosong ditolak
    bad = asyncio.run(tool.run({"prompt": ""}, ctx))
    assert not bad.ok


def test_generate_ppt_tool_builds_deck(client):
    from app.config import settings
    from app.tools import ToolContext, get_tool

    tool = get_tool("generate_ppt")
    ctx = ToolContext(settings=settings, conversation_id="cx", run_id="rx")
    res = asyncio.run(tool.run({
        "title": "Rencana Rilis",
        "slides": [
            {"title": "Ringkasan", "bullets": ["Target kuartal 4",
                                               "Fokus RAG"]},
            {"title": "Risiko", "bullets": ["Latensi model lokal"]},
        ],
    }, ctx))
    assert res.ok, res.data
    art = res.data["artifact"]
    assert art["kind"] == "pptx" and art["slide_count"] == 2
    stored = artifacts.read_artifact(art["id"], settings=settings)
    data = stored[1]
    assert data[:2] == b"PK"                       # zip OOXML valid
    assert b"ppt/presentation.xml" in data

    # outline tidak valid → error rapi, bukan crash
    bad = asyncio.run(tool.run({"title": "x"}, ctx))
    assert not bad.ok

    # download endpoint mengembalikan pptx
    r = client.get(f"/api/artifacts/{art['id']}/download")
    assert r.status_code == 200
    assert "presentationml" in r.headers["content-type"]


def test_ppt_image_mode_end_to_end_mock(client):
    """Mode PPT lewat chat mock: tool dipanggil, artifact terecord di trace."""
    import json as _json

    from app import db
    with client.stream("POST", "/api/chat",
                       json={"message": "buat deck onboarding karyawan",
                             "mode": "ppt"}) as r:
        evs = [_json.loads(l[6:]) for l in r.iter_lines()
               if l.startswith("data: ")]
    types = [e["type"] for e in evs]
    assert "artifact" in types
    art_ev = next(e for e in evs if e["type"] == "artifact")
    assert art_ev["kind"] == "pptx" and art_ev["tool"] == "generate_ppt"
    done = next(e for e in evs if e["type"] == "agent_done")
    assert art_ev["url"] in done["answer"]
    # meta trace mencatat mode
    meta = next(e for e in evs if e["type"] == "meta")
    assert meta["mode"] == "ppt"
