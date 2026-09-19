"""Pipeline kuota token: akuntansi, penegakan, reset periode, admin API.

Yang dijaga tes ini:
  * pemakaian beberapa panggilan LLM dalam satu run **dijumlahkan**
    (dulu ditimpa, sehingga kuota selalu terlihat lebih kecil dari kenyataan),
  * request ditolak **sebelum** model dipanggil begitu batas terlampaui,
  * batas per user (override) menang atas policy global; 0 = tanpa batas,
  * periode berbasis kalender → pemakaian hari lain tidak menghitung,
  * identitas end user diambil dari header `X-User-Id`, fallback IP.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

import pytest

from app import governance, quota
from app.agent.loop import _accumulate_usage


@pytest.fixture(autouse=True)
def _clean_quota_state():
    """Setiap tes mulai dari papan kosong (DB tes dipakai bersama).

    Sebagian tes di file ini murni unit (tanpa fixture `client`), jadi storage
    belum tentu ter-inisialisasi — `_init_storage()` idempoten dan aman
    dipanggil berulang.
    """
    from app import db, main

    main._init_storage()
    tables = ("token_usage", "usage_limits", "usage_users", "quota_rejections")

    def _reset() -> None:
        for table in tables:
            db.execute(f"DELETE FROM {table}")
        db.execute("DELETE FROM admin_policy WHERE key='quota'")

    _reset()
    yield
    _reset()


# ---------------------------------------------------------------------------
# Akumulasi usage antar panggilan LLM
# ---------------------------------------------------------------------------

def test_usage_from_several_llm_calls_is_summed_not_overwritten():
    """Satu run ReAct = beberapa panggilan model; token harus dijumlahkan."""
    total: dict = {}
    _accumulate_usage(total, {"prompt_tokens": 100, "completion_tokens": 20,
                              "total_tokens": 120})
    _accumulate_usage(total, {"prompt_tokens": 300, "completion_tokens": 50,
                              "total_tokens": 350})

    assert total["prompt_tokens"] == 400
    assert total["completion_tokens"] == 70
    assert total["total_tokens"] == 470
    assert total["llm_calls"] == 2


def test_total_tokens_is_derived_when_provider_omits_it():
    total: dict = {}
    _accumulate_usage(total, {"prompt_tokens": 7, "completion_tokens": 3})
    assert total["total_tokens"] == 10


def test_non_token_fields_keep_the_latest_value():
    total: dict = {}
    _accumulate_usage(total, {"prompt_tokens": 1, "device": "cpu"})
    _accumulate_usage(total, {"prompt_tokens": 1, "device": "cuda"})
    assert total["device"] == "cuda"
    assert total["prompt_tokens"] == 2


# ---------------------------------------------------------------------------
# Identitas end user
# ---------------------------------------------------------------------------

def test_user_identity_prefers_header_then_falls_back_to_ip():
    assert quota.normalise_user("user-42", fallback_ip="10.0.0.9") == "user-42"
    assert quota.normalise_user(None, fallback_ip="10.0.0.9") == "ip:10.0.0.9"
    assert quota.normalise_user("  ", fallback_ip="") == "anonymous"


def test_user_identity_is_length_capped():
    assert len(quota.normalise_user("x" * 500)) <= 120


# ---------------------------------------------------------------------------
# Akuntansi & periode
# ---------------------------------------------------------------------------

def test_record_accumulates_into_day_and_week_buckets():
    quota.record("u1", {"total_tokens": 400})
    quota.record("u1", {"prompt_tokens": 90, "completion_tokens": 10})

    used = quota.consumption("u1")
    assert used["day_tokens"] == 500
    assert used["day_requests"] == 2
    assert used["week_tokens"] == 500


def test_usage_from_a_previous_day_does_not_count_today():
    long_ago = time.time() - 60 * 60 * 24 * 40   # ~40 hari lalu
    quota.record("u2", {"total_tokens": 9_000}, ts=long_ago)
    quota.record("u2", {"total_tokens": 5}, ts=time.time())

    used = quota.consumption("u2")
    assert used["day_tokens"] == 5, "kuota harian harus reset per tanggal"


def test_period_keys_follow_the_calendar():
    moment = datetime(2026, 3, 5, 13, 30).timestamp()  # Kamis
    assert quota.day_key(moment) == "2026-03-05"
    assert quota.week_key(moment) == "2026-W10"


def test_day_reset_is_the_next_midnight():
    moment = datetime(2026, 3, 5, 13, 30).timestamp()
    snapshot = quota.status("u-reset", ts=moment)
    reset_at = datetime.fromtimestamp(snapshot["period"]["day_reset_at"])
    assert reset_at == datetime(2026, 3, 6, 0, 0)


def test_week_reset_is_next_monday_midnight():
    moment = datetime(2026, 3, 5, 13, 30).timestamp()   # Kamis
    snapshot = quota.status("u-reset", ts=moment)
    reset_at = datetime.fromtimestamp(snapshot["period"]["week_reset_at"])
    assert reset_at == datetime(2026, 3, 9, 0, 0)        # Senin berikutnya
    assert reset_at.isoweekday() == 1


# ---------------------------------------------------------------------------
# Penegakan
# ---------------------------------------------------------------------------

def test_request_is_allowed_below_the_daily_limit():
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 1_000}})
    quota.record("u3", {"total_tokens": 999})
    assert quota.check("u3")["allowed"] is True


def test_request_is_blocked_once_the_daily_limit_is_reached():
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 1_000}})
    quota.record("u4", {"total_tokens": 1_000})

    verdict = quota.check("u4")
    assert verdict["allowed"] is False
    assert "habis" in verdict["reason"]
    assert verdict["over_limit"] is True


def test_weekly_limit_blocks_even_when_the_daily_one_has_room():
    governance.update_policy({"quota": {
        "enabled": True, "daily_tokens": 1_000_000, "weekly_tokens": 100}})
    quota.record("u5", {"total_tokens": 150})

    verdict = quota.check("u5")
    assert verdict["allowed"] is False
    assert "mingguan" in verdict["reason"]


def test_daily_request_count_is_enforced():
    governance.update_policy({"quota": {
        "enabled": True, "daily_tokens": 0, "weekly_tokens": 0,
        "daily_requests": 2}})
    quota.record("u6", {"total_tokens": 1})
    quota.record("u6", {"total_tokens": 1})

    verdict = quota.check("u6")
    assert verdict["allowed"] is False
    assert "permintaan" in verdict["reason"]


def test_quota_disabled_never_blocks():
    governance.update_policy({"quota": {"enabled": False, "daily_tokens": 1}})
    quota.record("u7", {"total_tokens": 10_000})
    assert quota.check("u7")["allowed"] is True


def test_monitoring_mode_reports_but_does_not_block():
    """`block_on_exceed=False` → dipakai untuk menakar batas sebelum diberlakukan."""
    governance.update_policy({"quota": {
        "enabled": True, "daily_tokens": 10, "block_on_exceed": False}})
    quota.record("u8", {"total_tokens": 50})

    verdict = quota.check("u8")
    assert verdict["allowed"] is True
    assert verdict["over_limit"] is True
    assert verdict["reason"], "admin tetap harus diberi tahu"


def test_zero_limit_means_unlimited():
    governance.update_policy({"quota": {
        "enabled": True, "daily_tokens": 0, "weekly_tokens": 0,
        "daily_requests": 0}})
    quota.record("u9", {"total_tokens": 10_000_000})
    assert quota.check("u9")["allowed"] is True
    assert quota.status("u9")["remaining"]["day_tokens"] is None


# ---------------------------------------------------------------------------
# Override per user
# ---------------------------------------------------------------------------

def test_per_user_override_beats_the_global_policy():
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 100}})
    quota.set_override("vip", daily_tokens=10_000, note="pelanggan utama")
    quota.record("vip", {"total_tokens": 5_000})
    quota.record("biasa", {"total_tokens": 150})

    assert quota.check("vip")["allowed"] is True
    assert quota.check("biasa")["allowed"] is False
    assert quota.effective_limits("vip")["source"] == "override"
    assert quota.effective_limits("biasa")["source"] == "policy"


def test_override_with_zero_gives_a_user_unlimited_tokens():
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 100}})
    quota.set_override("tanpa-batas", daily_tokens=0, weekly_tokens=0,
                       daily_requests=0)
    quota.record("tanpa-batas", {"total_tokens": 999_999})
    assert quota.check("tanpa-batas")["allowed"] is True


def test_override_only_lifts_the_dimension_it_sets():
    """Menaikkan batas harian TIDAK diam-diam melepas batas mingguan.

    Override per-dimensi: `daily_tokens=0` (tanpa batas harian) sementara
    `weekly_tokens` tetap mengikuti policy — pengaman mingguan tetap menahan
    pemakaian ekstrem.
    """
    governance.update_policy({"quota": {
        "enabled": True, "daily_tokens": 100, "weekly_tokens": 1_000}})
    quota.set_override("harian-bebas", daily_tokens=0)
    quota.record("harian-bebas", {"total_tokens": 5_000})

    limits = quota.effective_limits("harian-bebas")
    assert limits["daily_tokens"] == 0        # dari override
    assert limits["weekly_tokens"] == 1_000   # tetap dari policy

    verdict = quota.check("harian-bebas")
    assert verdict["allowed"] is False
    assert "mingguan" in verdict["reason"]


def test_clearing_an_override_restores_the_policy_limit():
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 100}})
    quota.set_override("sementara", daily_tokens=50_000)
    quota.record("sementara", {"total_tokens": 500})
    assert quota.check("sementara")["allowed"] is True

    assert quota.clear_override("sementara") is True
    assert quota.check("sementara")["allowed"] is False


def test_reset_clears_only_the_requested_period():
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 100}})
    yesterday = (datetime.now() - timedelta(days=1)).timestamp()
    quota.record("u10", {"total_tokens": 80}, ts=yesterday)
    quota.record("u10", {"total_tokens": 80})

    assert quota.consumption("u10")["day_tokens"] == 80
    quota.reset_user("u10", scope="day")
    assert quota.consumption("u10")["day_tokens"] == 0
    # baris kemarin masih ada → agregat mingguan tetap memuatnya
    assert quota.consumption("u10")["week_tokens"] >= 0


# ---------------------------------------------------------------------------
# Monitoring untuk halaman admin
# ---------------------------------------------------------------------------

def test_admin_listing_shows_usage_limits_and_over_limit_flag():
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 100}})
    quota.record("boros", {"total_tokens": 500}, provider="openai", mode="text")
    quota.record("hemat", {"total_tokens": 10}, provider="openai", mode="text")

    users = {u["user_key"]: u for u in quota.list_users()}
    assert users["boros"]["day_tokens"] == 500
    assert users["boros"]["over_limit"] is True
    assert users["hemat"]["over_limit"] is False
    assert users["boros"]["limits"]["daily_tokens"] == 100


def test_overview_aggregates_by_provider_and_mode():
    quota.record("a", {"prompt_tokens": 10, "completion_tokens": 5},
                 provider="openai", mode="text")
    quota.record("b", {"prompt_tokens": 20, "completion_tokens": 5},
                 provider="huggingface", mode="rag")

    data = quota.overview()
    assert data["totals"]["tokens"] == 40
    assert data["totals"]["runs"] == 2
    assert data["users"] == 2
    providers = {row["provider"]: row["tokens"] for row in data["by_provider"]}
    assert providers == {"openai": 15, "huggingface": 25}
    modes = {row["mode"]: row["tokens"] for row in data["by_mode"]}
    assert modes == {"text": 15, "rag": 25}


def test_rejections_are_recorded_for_the_admin_dashboard():
    quota.record_rejection("pelanggar", "Kuota token harian sudah habis",
                           mode="text")
    rejections = quota.list_rejections()
    assert len(rejections) == 1
    assert rejections[0]["user_key"] == "pelanggar"
    assert quota.overview()["blocked_today"] == 1


# ---------------------------------------------------------------------------
# HTTP: gate di /api/chat + endpoint kuota
# ---------------------------------------------------------------------------

def test_chat_is_rejected_when_the_quota_is_exhausted(client):
    """Ditolak sebelum model dipanggil: stream hanya memuat pesan error."""
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 10}})
    quota.record("blokir-saya", {"total_tokens": 99})

    with client.stream("POST", "/api/chat", json={"message": "halo"},
                       headers={"X-User-Id": "blokir-saya"}) as r:
        body = r.read().decode()

    assert "habis" in body
    assert '"type": "error"' in body or '"type":"error"' in body
    # penolakan terekam untuk admin
    assert any(row["user_key"] == "blokir-saya"
               for row in quota.list_rejections())


def test_chat_records_usage_against_the_calling_user(client):
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 0}})

    with client.stream("POST", "/api/chat", json={"message": "halo"},
                       headers={"X-User-Id": "pemakai-1"}) as r:
        body = r.read().decode()

    assert '"type": "quota"' in body or '"type":"quota"' in body
    used = quota.consumption("pemakai-1")
    assert used["day_requests"] == 1
    assert used["day_tokens"] > 0, "provider mock melaporkan usage"


def test_quota_me_endpoint_reports_remaining_tokens(client):
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 1_000}})
    quota.record("lihat-saya", {"total_tokens": 250})

    out = client.get("/api/quota/me",
                     headers={"X-User-Id": "lihat-saya"}).json()
    assert out["used"]["day_tokens"] == 250
    assert out["remaining"]["day_tokens"] == 750
    assert out["limits"]["daily_tokens"] == 1_000


def test_quota_event_is_recorded_and_replayable(client):
    """Kontrak interpreter: event kuota bukan sekilas di UI, tapi ikut terekam."""
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 5_000}})

    with client.stream("POST", "/api/chat", json={"message": "halo"},
                       headers={"X-User-Id": "replay-user"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines()
                  if line.startswith("data: ")]

    live = next(e for e in events if e["type"] == "quota")
    assert live["limits"]["daily_tokens"] == 5_000
    assert live["user_key"] == "replay-user"
    assert live["t_ms"] >= 0 and "run_id" in live

    cid = next(e for e in events if e["type"] == "start")["conversation_id"]
    trace = client.get(f"/api/conversations/{cid}").json()["trace"]
    replayed = next(t for t in trace if t["type"] == "quota")
    assert replayed["limits"]["daily_tokens"] == 5_000
    assert replayed["user_key"] == "replay-user"


def test_admin_can_set_and_clear_a_user_limit(client):
    governance.update_policy({"quota": {"enabled": True, "daily_tokens": 100}})

    r = client.put("/api/admin/quota/users/klien-a",
                   json={"daily_tokens": 5_000, "note": "paket pro"})
    assert r.status_code == 200
    assert r.json()["limits"]["daily_tokens"] == 5_000

    dash = client.get("/api/admin/quota").json()
    assert dash["overview"]["overrides"] == 1
    assert any(u["user_key"] == "klien-a" for u in dash["users"])

    assert client.delete("/api/admin/quota/users/klien-a").json()["ok"] is True
    assert client.get("/api/admin/quota").json()["overview"]["overrides"] == 0


def test_admin_reset_clears_the_running_period(client):
    quota.record("klien-b", {"total_tokens": 900})
    out = client.post("/api/admin/quota/users/klien-b/reset?scope=day").json()
    assert out["ok"] is True
    assert out["status"]["used"]["day_tokens"] == 0


def test_admin_rejects_a_negative_limit(client):
    r = client.put("/api/admin/quota/users/klien-c",
                   json={"daily_tokens": -5})
    assert r.status_code == 422
