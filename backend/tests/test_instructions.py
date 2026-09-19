"""Pipeline instruksi advanced: playbook domain + teori cara menjawab.

Yang dijaga tes ini:
  * playbook menyala sesuai aturan aktivasi (always / keywords / manual),
  * pemicu dicocokkan sebagai **kata utuh** (bukan substring liar),
  * teori dari katalog benar-benar masuk ke system prompt sebagai prosedur,
  * prioritas menentukan urutan & batas jumlah playbook aktif,
  * pemakaian nyata terekam untuk monitoring admin (bukan hanya daftar),
  * blok instruksi ikut ter-trace sehingga bisa di-replay.
"""
from __future__ import annotations

import json

import pytest

from app import governance, instructions


@pytest.fixture(autouse=True)
def _clean_instructions():
    from app import db, main

    main._init_storage()

    def _reset() -> None:
        db.execute("DELETE FROM instruction_playbooks")
        db.execute("DELETE FROM instruction_activations")
        db.execute("DELETE FROM admin_policy WHERE key='instructions'")

    _reset()
    yield
    _reset()


def _legal_playbook(**overrides):
    payload = dict(
        name="Analis Hukum Perdata",
        domain="hukum",
        persona="analis hukum perdata Indonesia",
        theory="irac",
        rules="jangan memberi nasihat hukum final",
        output_format="Isu / Aturan / Analisis / Simpulan",
        triggers=["pasal", "wanprestasi", "kontrak"],
        activation="keywords",
        priority=200,
    )
    payload.update(overrides)
    return instructions.add_playbook(**payload)


# ---------------------------------------------------------------------------
# CRUD & validasi
# ---------------------------------------------------------------------------

def test_playbook_is_stored_with_theory_and_triggers():
    playbook = _legal_playbook()
    assert playbook["theory"] == "irac"
    assert playbook["triggers"] == ["pasal", "wanprestasi", "kontrak"]
    assert playbook["enabled"] is True


def test_unknown_theory_is_rejected():
    with pytest.raises(ValueError, match="tidak dikenal"):
        _legal_playbook(theory="tidak-ada")


def test_playbook_without_any_directive_is_rejected():
    """Playbook kosong tidak akan mengubah perilaku — tolak lebih awal."""
    with pytest.raises(ValueError, match="minimal"):
        instructions.add_playbook(name="Kosong", domain="apa saja")


def test_blank_name_is_rejected():
    with pytest.raises(ValueError, match="nama"):
        instructions.add_playbook(name="   ", persona="x")


def test_theory_catalog_exposes_ready_made_frameworks():
    keys = {t["key"] for t in instructions.theory_catalog()}
    assert {"irac", "soap", "minto", "feynman", "socratic"} <= keys
    for theory in instructions.theory_catalog():
        assert theory["method"].strip(), theory["key"]
        assert theory["label"].strip()


# ---------------------------------------------------------------------------
# Aktivasi
# ---------------------------------------------------------------------------

def test_keyword_activation_only_fires_on_a_trigger():
    _legal_playbook()
    assert instructions.select_playbooks("apa akibat wanprestasi kontrak?")
    assert not instructions.select_playbooks("resep nasi goreng enak")


def test_trigger_matching_uses_whole_words():
    """Pemicu pendek tidak boleh menyala di tengah kata lain."""
    _legal_playbook(name="Pajak", triggers=["pph"], theory="", persona="ahli pajak")
    assert instructions.select_playbooks("bagaimana hitung pph 21?")
    assert not instructions.select_playbooks("lihat pphotograph ini")


def test_always_activation_fires_without_any_keyword():
    instructions.add_playbook(name="Gaya Rumah", activation="always",
                              persona="asisten yang ringkas dan runtut",
                              priority=10)
    selected = instructions.select_playbooks("halo")
    assert [p["name"] for p in selected] == ["Gaya Rumah"]
    assert selected[0]["match_reason"] == "selalu aktif"


def test_manual_playbook_needs_an_explicit_id():
    playbook = _legal_playbook(activation="manual")
    assert not instructions.select_playbooks("wanprestasi kontrak pasal")
    selected = instructions.select_playbooks("apa saja", playbook_ids=[playbook["id"]])
    assert [p["id"] for p in selected] == [playbook["id"]]
    assert selected[0]["match_reason"] == "dipilih eksplisit"


def test_disabled_playbook_never_fires():
    playbook = _legal_playbook()
    instructions.update_playbook(playbook["id"], {"enabled": False})
    assert not instructions.select_playbooks("wanprestasi")


def test_playbook_can_be_scoped_to_certain_modes():
    _legal_playbook(modes=["rag"])
    assert not instructions.select_playbooks("pasal 1365", mode="text")
    assert instructions.select_playbooks("pasal 1365", mode="rag")


def test_higher_priority_comes_first_and_max_active_caps_the_list():
    instructions.add_playbook(name="Rendah", activation="always",
                              persona="a", priority=1)
    instructions.add_playbook(name="Tinggi", activation="always",
                              persona="b", priority=999)
    instructions.add_playbook(name="Sedang", activation="always",
                              persona="c", priority=500)

    names = [p["name"] for p in instructions.select_playbooks("x", max_active=2)]
    assert names == ["Tinggi", "Sedang"]


# ---------------------------------------------------------------------------
# Injeksi ke system prompt
# ---------------------------------------------------------------------------

def test_selected_theory_is_injected_as_a_procedure():
    _legal_playbook()
    block, selected = instructions.prompt_block("soal wanprestasi kontrak")

    assert len(selected) == 1
    assert instructions.PROMPT_HEADING in block
    assert "Analis Hukum Perdata" in block
    assert "IRAC" in block
    # bukan sekadar nama teori: langkah-langkahnya ikut masuk
    assert "ISU" in block and "SIMPULAN" in block
    assert "jangan memberi nasihat hukum final" in block
    assert "Isu / Aturan / Analisis / Simpulan" in block


def test_free_form_method_is_used_when_no_theory_is_chosen():
    instructions.add_playbook(name="Gaya Bebas", activation="always",
                              method="jawab dengan tiga poin lalu satu contoh")
    block, _ = instructions.prompt_block("apa saja")
    assert "METODE MENJAWAB: jawab dengan tiga poin" in block


def test_block_is_empty_when_the_pipeline_is_disabled():
    _legal_playbook()
    block, selected = instructions.prompt_block(
        "wanprestasi", policy_instructions={"enabled": False})
    assert block == "" and selected == []


def test_block_is_truncated_to_the_policy_limit():
    instructions.add_playbook(name="Panjang", activation="always",
                              persona="x" * 5_000)
    block, _ = instructions.prompt_block(
        "apa saja", policy_instructions={"enabled": True, "max_active": 3,
                                         "max_chars": 500})
    assert len(block) <= 560
    assert "dipotong" in block


def test_no_playbook_yields_an_empty_block():
    block, selected = instructions.prompt_block("halo")
    assert block == "" and selected == []


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

def test_activation_is_recorded_for_monitoring():
    playbook = _legal_playbook()
    _, selected = instructions.prompt_block("wanprestasi")
    instructions.record_activation(selected, conversation_id="c1",
                                   run_id="r1", mode="text")

    stats = instructions.stats()
    assert stats["activations_total"] == 1
    assert stats["top_used"][0]["playbook_id"] == playbook["id"]
    assert stats["top_used"][0]["runs"] == 1


def test_stats_flags_enabled_playbooks_that_never_fired():
    """Playbook aktif tapi tak pernah terpakai = pemicunya kemungkinan salah."""
    _legal_playbook(name="Tak Pernah", triggers=["katayangtidakpernahmuncul"])
    never = [p["name"] for p in instructions.stats()["never_used"]]
    assert "Tak Pernah" in never


def test_stats_counts_playbooks_per_activation_mode():
    _legal_playbook()
    instructions.add_playbook(name="Selalu", activation="always", persona="a")
    stats = instructions.stats()
    assert stats["total"] == 2
    assert stats["by_activation"]["keywords"] == 1
    assert stats["by_activation"]["always"] == 1


# ---------------------------------------------------------------------------
# HTTP: admin API + jejak di interpreter
# ---------------------------------------------------------------------------

def test_admin_can_manage_playbooks(client):
    created = client.post("/api/admin/instructions", json={
        "name": "Konsultan Bisnis", "domain": "strategi",
        "theory": "minto", "activation": "always", "priority": 300,
    })
    assert created.status_code == 200, created.text
    pid = created.json()["id"]

    listing = client.get("/api/admin/instructions").json()
    assert any(p["id"] == pid for p in listing["playbooks"])
    assert listing["stats"]["enabled"] == 1
    assert any(t["key"] == "minto" for t in listing["theories"])

    patched = client.patch(f"/api/admin/instructions/{pid}",
                           json={"enabled": False})
    assert patched.json()["enabled"] is False

    assert client.delete(f"/api/admin/instructions/{pid}").json()["ok"] is True
    assert client.delete(f"/api/admin/instructions/{pid}").status_code == 404


def test_admin_rejects_an_unknown_theory_over_http(client):
    r = client.post("/api/admin/instructions",
                    json={"name": "X", "theory": "bukan-teori"})
    assert r.status_code == 422


def test_admin_preview_shows_which_playbook_would_fire(client):
    client.post("/api/admin/instructions", json={
        "name": "Klinis", "theory": "soap", "activation": "keywords",
        "triggers": ["demam", "batuk"],
    })
    hit = client.post("/api/admin/instructions/preview",
                      json={"message": "anak saya demam 3 hari"}).json()
    assert hit["count"] == 1
    assert "SUBJEKTIF" in hit["block"]

    miss = client.post("/api/admin/instructions/preview",
                       json={"message": "harga saham hari ini"}).json()
    assert miss["count"] == 0 and miss["block"] == ""


def test_instructions_event_is_traced_and_replayable(client):
    client.post("/api/admin/instructions", json={
        "name": "Tutor Fisika", "theory": "feynman", "activation": "always",
    })

    with client.stream("POST", "/api/chat",
                       json={"message": "jelaskan gravitasi"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines()
                  if line.startswith("data: ")]

    live = next(e for e in events if e["type"] == "instructions")
    assert live["count"] == 1
    assert live["playbooks"][0]["theory_label"].startswith("Teknik Feynman")
    assert "analogi" in live["block"]

    cid = next(e for e in events if e["type"] == "start")["conversation_id"]
    trace = client.get(f"/api/conversations/{cid}").json()["trace"]
    replayed = next(t for t in trace if t["type"] == "instructions")
    assert replayed["playbooks"][0]["name"] == "Tutor Fisika"


def test_run_records_the_playbook_it_used(client):
    client.post("/api/admin/instructions", json={
        "name": "Selalu Aktif", "theory": "stepwise", "activation": "always",
    })
    with client.stream("POST", "/api/chat", json={"message": "2+2 berapa"}) as r:
        r.read()

    dashboard = client.get("/api/admin/instructions").json()
    assert dashboard["stats"]["activations_total"] >= 1
    assert dashboard["activations"][0]["playbook_name"] == "Selalu Aktif"


def test_policy_can_disable_the_whole_instruction_pipeline(client):
    client.post("/api/admin/instructions", json={
        "name": "Mati", "theory": "irac", "activation": "always"})
    governance.update_policy({"instructions": {"enabled": False}})

    with client.stream("POST", "/api/chat", json={"message": "halo"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines()
                  if line.startswith("data: ")]

    live = next(e for e in events if e["type"] == "instructions")
    assert live["count"] == 0 and live["block"] == ""
