"""Genera reports/auditoria_ejemplo.md con datos de prueba, sin red y sin ejecutar servidores.

Uso: python scripts/auditoria_ejemplo.py
- skills: ejemplos/ (los ejemplos que ya trae el repo)
- config: tests/fixtures/cve/claude_desktop_config.json
- OSV: respuesta guardada en tests/fixtures/cve/osv (mcp-remote 0.1.15 → CVE-2025-6514, dato real)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agentguard.audit import build, render  # noqa: E402
from agentguard.cve import osv  # noqa: E402
from agentguard.i18n import set_lang  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "cve"
SAVED = {"mcp-remote": "GHSA-6xpm-ggf7-wc3p"}  # solo vulnerabilidades reales guardadas como fixture


def offline_check(packages):
    def post(url, payload):
        return {"results": [{"vulns": [{"id": SAVED[q["package"]["name"]]}]} if q["package"]["name"] in SAVED
                            else {} for q in payload["queries"]]}

    def get(url):
        return json.loads((FIX / "osv" / f"{url.rsplit('/', 1)[1]}.json").read_text(encoding="utf-8"))

    return osv.check(packages, post, get)


def main() -> int:
    os.chdir(ROOT)  # rutas relativas al repo en el reporte
    config = FIX / "claude_desktop_config.json"
    scopes = {
        "es": ("auditoria_ejemplo.md", "ejemplo con fixtures: skills `ejemplos`, config "
                                       "`tests/fixtures/cve/claude_desktop_config.json`, OSV guardado"),
        "en": ("audit_example_en.md", "fixture example: skills `ejemplos`, config "
                                      "`tests/fixtures/cve/claude_desktop_config.json`, saved OSV data"),
    }
    for lang, (name, scope) in scopes.items():
        set_lang(lang)
        audit = build(skills=ROOT / "ejemplos", config=config, check_fn=offline_check)
        out = ROOT / "reports" / name
        out.write_text(render(audit, date(2026, 11, 2), scope), encoding="utf-8")
        print(f"{len(audit.items)} hallazgo(s) -> {out}")
    set_lang("es")
    return 0


if __name__ == "__main__":
    sys.exit(main())
