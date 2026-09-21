"""Hasilkan `docs/internship/03-rencana-sprint.md` dari `internship_plan.py`.

Rencana sprint punya satu sumber kebenaran: modul `backend/app/internship_plan.py`
(yang juga mengisi papan `/internship`). Dokumen ringkasannya dibuat ulang oleh
skrip ini supaya tidak pernah berbeda dari papan.

    python scripts/gen_internship_docs.py            # tulis dokumen
    python scripts/gen_internship_docs.py --check    # gagal bila dokumen basi
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import internship_plan as plan  # noqa: E402

OUT = ROOT / "docs" / "internship" / "03-rencana-sprint.md"


def _epic_of(task: dict) -> str:
    names = {e["label"]: e["name"] for e in plan.EPICS}
    for label in task["labels"]:
        if label in names:
            return names[label].split(" — ")[0]
    return "-"


def render() -> str:
    summary = plan.summary()
    lines: list[str] = [
        "# Rencana sprint — proyek chatbot LLM",
        "",
        "> Dokumen ini **dihasilkan otomatis** dari `backend/app/internship_plan.py`",
        "> (`python scripts/gen_internship_docs.py`). Jangan disunting manual —",
        "> ubah rencananya, lalu jalankan ulang skripnya.",
        "",
        f"Total **{summary['total']} task**, estimasi "
        f"**{summary['estimate_days']} hari kerja**, dipecah menjadi "
        f"{len(plan.PHASES)} sprint. Papan: `/internship` (id `INT-NNN`).",
        "",
        "## Aturan kolom",
        "",
        "Hanya task **Sprint 0** yang berada di kolom *To do*; sprint berikutnya",
        "menunggu di *Backlog* dan baru ditarik saat sprint sebelumnya ditutup.",
        "Gerbang Sprint 0: **PRD rampung dan disetujui** sebelum kode fitur ditulis.",
        "",
        "## Epic",
        "",
        "| Label | Epic |",
        "|---|---|",
    ]
    for epic in plan.EPICS:
        lines.append(f"| `{epic['label']}` | {epic['name']} |")
    lines += ["", "## Sprint", ""]

    for phase in plan.PHASES:
        tasks = plan.by_phase(phase["id"])
        days = round(sum(float(t["estimate"] or 0) for t in tasks), 1)
        lines += [
            f"### {phase['name']}",
            "",
            f"{phase['subtitle']}  ",
            f"*{len(tasks)} task · {days} hari · label `"
            f"{plan.SPRINT_LABELS[phase['id']]}`*",
            "",
            "| Id | Task | Epic | Hari | Prioritas | Prasyarat |",
            "|---|---|---|---|---|---|",
        ]
        for task in tasks:
            deps = ", ".join(task["depends_on"]) or "-"
            lines.append(
                f"| `{task['id']}` | {task['title']} | {_epic_of(task)} | "
                f"{task['estimate']} | {task['priority']} | {deps} |")
        lines.append("")

    lines += [
        "## Definisi selesai",
        "",
        "Kriteria selesai tiap task ada di papan `/internship` (tab *Kriteria",
        "selesai*) dan harus terpenuhi seluruhnya — lihat",
        "[04-definition-of-done.md](04-definition-of-done.md).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT.relative_to(ROOT)} basi — jalankan "
                  f"`python scripts/gen_internship_docs.py`")
            return 1
        print(f"{OUT.relative_to(ROOT)} sudah sesuai rencana.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"ditulis: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
