"""Pipeline instruksi advanced — persona domain + *teori cara menjawab*.

Masalah yang diselesaikan: memori (`memory.py`) bagus untuk fakta & pedoman
pendek, tetapi tidak cukup untuk menjadikan asisten ini ahli pada satu domain
dengan **metode menjawab tertentu**. Modul ini menambah lapisan *playbook*:

    playbook = domain (siapa saya)          →  "analis hukum perdata Indonesia"
             + method (bagaimana menjawab)  →  kerangka IRAC
             + rules  (batasan)             →  "jangan memberi nasihat final"
             + format (bentuk keluaran)     →  "Isu / Aturan / Analisis / Simpulan"

Aktivasi (kolom `activation`):
  always    — selalu dipakai (mis. gaya rumah, bahasa, kerangka umum)
  keywords  — hanya bila pesan user memuat salah satu kata pemicu
  manual    — hanya bila dipanggil eksplisit lewat `playbook_ids`

Semua playbook yang aktif dirangkai menjadi satu blok di system prompt setiap
run, **dan** direkam sebagai event `instructions` di Mechanistic Interpreter +
tabel `instruction_activations` — jadi admin bisa melihat playbook mana yang
benar-benar terpakai, bukan hanya yang terdaftar.

Katalog `THEORIES` menyediakan teori cara menjawab siap pakai (IRAC, SOAP,
Piramida Minto, Feynman, Socratic, …) supaya admin tidak perlu menulis
kerangka metodologis dari nol; `method` bebas diisi manual bila perlu.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from . import db

ACTIVATIONS = ("always", "keywords", "manual")

PROMPT_HEADING = "INSTRUKSI ADVANCED (playbook domain — atur di halaman admin):"


# ---------------------------------------------------------------------------
# Katalog teori cara menjawab
# ---------------------------------------------------------------------------
#: Setiap entri: kerangka langkah yang dimasukkan ke system prompt. Sengaja
#: ditulis sebagai *prosedur*, bukan deskripsi, supaya model mengikutinya.
THEORIES: dict[str, dict[str, str]] = {
    "irac": {
        "label": "IRAC (analisis hukum)",
        "domain_hint": "hukum, kepatuhan, kontrak",
        "method": (
            "Gunakan kerangka IRAC secara eksplisit dan berurutan:\n"
            "1. ISU — rumuskan pertanyaan hukum yang sebenarnya ditanyakan.\n"
            "2. ATURAN — sebutkan norma/pasal/doktrin yang relevan beserta "
            "sumbernya; bila sumber tidak tersedia, katakan demikian.\n"
            "3. ANALISIS — terapkan aturan pada fakta, bahas argumen yang "
            "berlawanan sebelum menyimpulkan.\n"
            "4. SIMPULAN — jawab isu secara langsung, sertakan tingkat "
            "keyakinan dan syarat yang membuat simpulan berubah."
        ),
    },
    "soap": {
        "label": "SOAP (penalaran klinis)",
        "domain_hint": "kesehatan, triase informasi medis",
        "method": (
            "Gunakan kerangka SOAP:\n"
            "1. SUBJEKTIF — keluhan/konteks yang disampaikan penanya.\n"
            "2. OBJEKTIF — data terukur yang tersedia; tandai yang tidak ada.\n"
            "3. ASSESSMENT — kemungkinan penjelasan, diurut dari yang paling "
            "mungkin, sertakan pembanding (diagnosis diferensial).\n"
            "4. PLAN — langkah selanjutnya yang bisa ditindaklanjuti.\n"
            "Selalu tegaskan ini informasi edukatif, bukan diagnosis medis."
        ),
    },
    "minto": {
        "label": "Piramida Minto (konsultan)",
        "domain_hint": "bisnis, strategi, rekomendasi manajemen",
        "method": (
            "Gunakan Prinsip Piramida:\n"
            "1. Mulai dari JAWABAN/rekomendasi di kalimat pertama.\n"
            "2. Dukung dengan 3 argumen utama yang saling eksklusif dan "
            "bersama-sama menyeluruh (MECE).\n"
            "3. Baru turunkan data/bukti pendukung tiap argumen.\n"
            "4. Tutup dengan risiko utama dan langkah berikutnya."
        ),
    },
    "feynman": {
        "label": "Teknik Feynman (mengajar)",
        "domain_hint": "edukasi, penjelasan konsep",
        "method": (
            "Gunakan Teknik Feynman:\n"
            "1. Jelaskan inti konsep dengan bahasa sederhana tanpa jargon.\n"
            "2. Gunakan satu analogi konkret dari kehidupan sehari-hari.\n"
            "3. Tunjukkan di mana orang biasanya salah paham.\n"
            "4. Tutup dengan definisi presisi beserta istilah teknisnya."
        ),
    },
    "socratic": {
        "label": "Socratic (membimbing, bukan menyuapi)",
        "domain_hint": "tutor, coaching, pelatihan",
        "method": (
            "Bimbing dengan metode Socratic:\n"
            "1. Periksa apa yang sudah dipahami penanya.\n"
            "2. Ajukan satu pertanyaan penuntun yang memancing langkah "
            "berikutnya, jangan langsung memberi jawaban akhir.\n"
            "3. Beri petunjuk bertingkat bila penanya tersendat.\n"
            "4. Setelah penanya sampai pada kesimpulan, rangkum dan perbaiki.\n"
            "Bila penanya meminta jawaban langsung, penuhi permintaannya."
        ),
    },
    "hypothesis": {
        "label": "Hypothesis-driven (investigasi/debug)",
        "domain_hint": "teknis, debugging, analisis akar masalah",
        "method": (
            "Bekerja berbasis hipotesis:\n"
            "1. Nyatakan gejala yang teramati secara terukur.\n"
            "2. Daftar hipotesis penyebab beserta cara mengujinya.\n"
            "3. Urutkan pengujian dari yang paling murah & paling "
            "memangkas kemungkinan.\n"
            "4. Bedakan dengan jelas mana yang SUDAH terbukti oleh bukti dan "
            "mana yang masih dugaan.\n"
            "5. Simpulkan akar masalah + perbaikan, sebutkan yang belum teruji."
        ),
    },
    "toulmin": {
        "label": "Toulmin (argumentasi ketat)",
        "domain_hint": "analisis kebijakan, esai argumentatif",
        "method": (
            "Susun argumen dengan model Toulmin: KLAIM, DATA (bukti), "
            "WARRANT (mengapa data mendukung klaim), QUALIFIER (batas "
            "keberlakuan), dan REBUTTAL (kondisi yang menggugurkan klaim). "
            "Nyatakan tiap bagian secara eksplisit."
        ),
    },
    "star": {
        "label": "STAR (perilaku & studi kasus)",
        "domain_hint": "HR, wawancara, evaluasi kinerja",
        "method": (
            "Gunakan STAR: SITUATION, TASK, ACTION, RESULT — dengan hasil "
            "yang terukur di bagian akhir."
        ),
    },
    "stepwise": {
        "label": "Penalaran bertahap + verifikasi",
        "domain_hint": "umum, matematika, prosedur",
        "method": (
            "Kerjakan bertahap: uraikan langkah, tunjukkan perhitungan/"
            "alasan tiap langkah, lalu VERIFIKASI hasil dengan cara kedua "
            "(estimasi kasar, satuan, atau uji balik) sebelum menyimpulkan. "
            "Bila verifikasi gagal, perbaiki dan katakan apa yang salah."
        ),
    },
}


def theory_catalog() -> list[dict[str, str]]:
    """Katalog untuk dropdown di halaman admin."""
    return [{"key": key, **value} for key, value in THEORIES.items()]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def _row_to_playbook(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    row["enabled"] = bool(row["enabled"])
    for field in ("triggers", "modes"):
        try:
            row[field] = json.loads(row.get(field) or "[]")
        except (TypeError, ValueError):
            row[field] = []
    return row


def add_playbook(*, name: str, domain: str = "", persona: str = "",
                 method: str = "", theory: str = "", rules: str = "",
                 output_format: str = "", triggers: list[str] | None = None,
                 modes: list[str] | None = None, activation: str = "keywords",
                 priority: int = 100, enabled: bool = True) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("nama playbook tidak boleh kosong")
    if activation not in ACTIVATIONS:
        raise ValueError(f"activation harus salah satu dari: {', '.join(ACTIVATIONS)}")
    theory = (theory or "").strip().lower()
    if theory and theory not in THEORIES:
        raise ValueError(f"teori '{theory}' tidak dikenal")
    # Playbook tanpa arahan apa pun tidak akan mengubah perilaku — tolak lebih
    # awal daripada diam-diam jadi entri kosong di prompt.
    if not any((persona.strip(), method.strip(), theory, rules.strip(),
                output_format.strip())):
        raise ValueError("playbook harus memuat minimal persona, method, "
                         "theory, rules, atau output_format")

    pid = uuid.uuid4().hex[:12]
    ts = time.time()
    db.execute(
        "INSERT INTO instruction_playbooks(id, name, domain, persona, method, "
        "theory, rules, output_format, triggers, modes, activation, priority, "
        "enabled, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, name, domain.strip(), persona.strip(), method.strip(), theory,
         rules.strip(), output_format.strip(),
         json.dumps([t.strip() for t in (triggers or []) if t.strip()]),
         json.dumps([m.strip() for m in (modes or []) if m.strip()]),
         activation, int(priority), 1 if enabled else 0, ts, ts),
    )
    return get_playbook(pid) or {}


def get_playbook(pid: str) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM instruction_playbooks WHERE id=?", (pid,))
    return _row_to_playbook(row) if row else None


def list_playbooks(include_disabled: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT * FROM instruction_playbooks"
    if not include_disabled:
        sql += " WHERE enabled=1"
    sql += " ORDER BY priority DESC, updated_at DESC"
    return [_row_to_playbook(r) for r in db.query_all(sql)]


def update_playbook(pid: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    current = get_playbook(pid)
    if not current:
        return None
    fields: list[str] = []
    params: list[Any] = []
    for key in ("name", "domain", "persona", "method", "rules",
                "output_format", "activation", "theory"):
        if patch.get(key) is not None:
            value = str(patch[key]).strip()
            if key == "activation" and value not in ACTIVATIONS:
                raise ValueError("activation tidak dikenal")
            if key == "theory":
                value = value.lower()
                if value and value not in THEORIES:
                    raise ValueError(f"teori '{value}' tidak dikenal")
            fields.append(f"{key}=?")
            params.append(value)
    for key in ("triggers", "modes"):
        if patch.get(key) is not None:
            fields.append(f"{key}=?")
            params.append(json.dumps(
                [str(x).strip() for x in patch[key] if str(x).strip()]))
    if patch.get("priority") is not None:
        fields.append("priority=?")
        params.append(int(patch["priority"]))
    if "enabled" in patch and patch["enabled"] is not None:
        fields.append("enabled=?")
        params.append(1 if patch["enabled"] else 0)
    if not fields:
        return current
    fields.append("updated_at=?")
    params.append(time.time())
    params.append(pid)
    db.execute(
        f"UPDATE instruction_playbooks SET {', '.join(fields)} WHERE id=?",
        tuple(params))
    return get_playbook(pid)


def delete_playbook(pid: str) -> bool:
    if not get_playbook(pid):
        return False
    db.execute("DELETE FROM instruction_playbooks WHERE id=?", (pid,))
    return True


# ---------------------------------------------------------------------------
# Seleksi & injeksi
# ---------------------------------------------------------------------------

def _matches_keyword(message: str, trigger: str) -> bool:
    """Cocokkan pemicu sebagai kata utuh bila memungkinkan.

    Substring mentah membuat pemicu pendek seperti "pph" ikut menyala pada
    "pphotograph"; batas kata (`\\b`) mencegah aktivasi playbook yang salah.
    """
    trigger = trigger.strip().lower()
    if not trigger:
        return False
    if re.fullmatch(r"[\w\s]+", trigger):
        return re.search(rf"\b{re.escape(trigger)}\b", message) is not None
    return trigger in message


def select_playbooks(message: str, *, mode: str = "text",
                     playbook_ids: list[str] | None = None,
                     max_active: int = 3) -> list[dict[str, Any]]:
    """Playbook yang berlaku untuk satu pesan, terurut prioritas."""
    message_lc = (message or "").lower()
    explicit = set(playbook_ids or [])
    chosen: list[dict[str, Any]] = []

    for playbook in list_playbooks(include_disabled=False):
        modes = playbook["modes"]
        if modes and mode not in modes:
            continue
        reason = ""
        if playbook["id"] in explicit:
            reason = "dipilih eksplisit"
        elif playbook["activation"] == "always":
            reason = "selalu aktif"
        elif playbook["activation"] == "keywords":
            hits = [t for t in playbook["triggers"]
                    if _matches_keyword(message_lc, t)]
            if hits:
                reason = "pemicu: " + ", ".join(hits[:5])
        if not reason:
            continue
        chosen.append({**playbook, "match_reason": reason})
        if len(chosen) >= max(1, max_active):
            break
    return chosen


def render_block(playbooks: list[dict[str, Any]], *,
                 max_chars: int = 4000) -> str:
    """Rangkai playbook terpilih menjadi satu blok system prompt."""
    if not playbooks:
        return ""
    lines = [PROMPT_HEADING]
    for playbook in playbooks:
        lines.append(f"\n### {playbook['name']}"
                     + (f" — domain: {playbook['domain']}"
                        if playbook["domain"] else ""))
        if playbook["persona"]:
            lines.append(f"PERAN: {playbook['persona']}")
        method = playbook["method"]
        theory_key = playbook["theory"]
        if theory_key and theory_key in THEORIES:
            theory = THEORIES[theory_key]
            lines.append(f"METODE MENJAWAB — {theory['label']}:")
            lines.append(theory["method"])
            if method:
                lines.append(f"Tambahan metode: {method}")
        elif method:
            lines.append(f"METODE MENJAWAB: {method}")
        if playbook["rules"]:
            lines.append(f"BATASAN: {playbook['rules']}")
        if playbook["output_format"]:
            lines.append(f"FORMAT KELUARAN: {playbook['output_format']}")
    lines.append(
        "\nIkuti playbook di atas untuk menyusun jawaban. Bila beberapa "
        "playbook aktif, yang tercantum lebih dulu berprioritas lebih tinggi. "
        "Playbook mengatur CARA menjawab — ia bukan sumber fakta dan tidak "
        "boleh disitasi sebagai sumber."
    )
    block = "\n".join(lines)
    if len(block) > max_chars:
        block = block[:max_chars].rstrip() + "\n… (playbook dipotong)"
    return block


def prompt_block(message: str, *, mode: str = "text",
                 policy_instructions: dict[str, Any] | None = None,
                 playbook_ids: list[str] | None = None
                 ) -> tuple[str, list[dict[str, Any]]]:
    """Blok prompt + daftar playbook yang dipakai (untuk trace & monitoring)."""
    policy_instructions = policy_instructions or {}
    if not policy_instructions.get("enabled", True):
        return "", []
    selected = select_playbooks(
        message, mode=mode, playbook_ids=playbook_ids,
        max_active=int(policy_instructions.get("max_active") or 3))
    block = render_block(
        selected, max_chars=int(policy_instructions.get("max_chars") or 4000))
    return block, selected


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

def record_activation(playbooks: list[dict[str, Any]], *,
                      conversation_id: str = "", run_id: str = "",
                      mode: str = "", ts: float | None = None) -> None:
    """Catat playbook yang benar-benar dipakai satu run."""
    moment = ts if ts is not None else time.time()
    for playbook in playbooks:
        db.execute(
            "INSERT INTO instruction_activations(id, playbook_id, playbook_name, "
            "conversation_id, run_id, mode, match_reason, ts) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex[:12], playbook["id"], playbook["name"],
             conversation_id, run_id, mode,
             playbook.get("match_reason", "")[:200], moment),
        )


def trace_payload(playbooks: list[dict[str, Any]], block: str) -> dict[str, Any]:
    """Payload event `instructions` untuk Mechanistic Interpreter."""
    return {
        "count": len(playbooks),
        "chars": len(block),
        "playbooks": [
            {
                "id": p["id"],
                "name": p["name"],
                "domain": p["domain"],
                "theory": p["theory"],
                "theory_label": THEORIES.get(p["theory"], {}).get("label", ""),
                "activation": p["activation"],
                "priority": p["priority"],
                "match_reason": p.get("match_reason", ""),
            }
            for p in playbooks
        ],
        # Blok persis yang masuk ke system prompt: interpreter harus
        # memperlihatkan instruksi apa adanya, bukan ringkasannya.
        "block": block,
    }


def stats() -> dict[str, Any]:
    """Ringkasan pipeline instruksi untuk dashboard admin."""
    playbooks = list_playbooks()
    usage = db.query_all(
        "SELECT playbook_id, playbook_name, COUNT(*) AS runs, MAX(ts) AS last_used "
        "FROM instruction_activations GROUP BY playbook_id "
        "ORDER BY runs DESC LIMIT 50")
    used = {row["playbook_id"]: row for row in usage}
    return {
        "total": len(playbooks),
        "enabled": sum(1 for p in playbooks if p["enabled"]),
        "by_activation": {
            activation: sum(1 for p in playbooks if p["activation"] == activation)
            for activation in ACTIVATIONS
        },
        "activations_total": int((db.query_one(
            "SELECT COUNT(*) AS n FROM instruction_activations") or {}).get("n") or 0),
        "top_used": usage,
        # Playbook aktif yang belum pernah terpakai: biasanya pemicunya salah.
        "never_used": [
            {"id": p["id"], "name": p["name"], "activation": p["activation"],
             "triggers": p["triggers"]}
            for p in playbooks if p["enabled"] and p["id"] not in used
        ],
    }


def recent_activations(limit: int = 100) -> list[dict[str, Any]]:
    return db.query_all(
        "SELECT * FROM instruction_activations ORDER BY ts DESC LIMIT ?",
        (int(limit),))
