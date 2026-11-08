"""Salida en inglés (--lang en / AGENTGUARD_LANG=en) sin cambiar la salida en español."""
from __future__ import annotations

import io
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentguard import i18n, scanner
from agentguard.audit import build, render
from agentguard.cli import main
from agentguard.trifecta import LABEL, load_known

ROOT = Path(__file__).resolve().parent.parent
SPANISH = re.compile(r"hallazgo|archivo\(s\)|servidor\(es\)|Cómo arreglar|Resumen|Tríada|tríada|Sin clasificar|"
                     r"Detalle|Alcance|Riesgo|ALTO|MEDIO|versión no fijada|no indica")


def run(*args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(["agentguard", *args])
    return code, buf.getvalue()


class TestI18n(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang("es")

    def test_pop_lang(self):
        self.assertEqual(i18n.pop_lang(["ag", "scan", "--lang", "en", "x"]), ["ag", "scan", "x"])
        self.assertEqual(i18n.get_lang(), "en")
        self.assertEqual(i18n.pop_lang(["ag", "--lang=es", "scan"]), ["ag", "scan"])
        self.assertEqual(i18n.get_lang(), "es")
        i18n.set_lang("xx")
        self.assertEqual(i18n.get_lang(), "es")

    def test_every_rule_and_label_has_english(self):
        rules = {name for _, name, _ in scanner.RULES} | {
            v for k, v in vars(scanner).items() if k.startswith("RULE_") and isinstance(v, str)}
        texts = rules | set(LABEL.values()) | {e["motivo"] for e in load_known()}
        missing = sorted(x for x in texts if x not in i18n.EN)
        self.assertEqual(missing, [])

    def test_scan_english(self):
        code, out = run("scan", str(ROOT / "ejemplos"), "--lang", "en")
        self.assertEqual(code, 1)
        self.assertIn("[HIGH] Asks to hide something from the user", out)
        self.assertIn("finding(s)", out)
        self.assertIsNone(SPANISH.search(out), out)

    def test_scan_spanish_by_default(self):
        _, out = run("scan", str(ROOT / "ejemplos"))
        self.assertIn("[ALTO] Pide ocultar algo al usuario", out)

    def test_trifecta_english(self):
        code, out = run("--lang", "en", "trifecta", str(ROOT / "tests/fixtures/trifecta/claude_proyecto_con_triada.json"))
        self.assertEqual(code, 1)
        self.assertIn("LETHAL TRIFECTA", out)
        self.assertIsNone(SPANISH.search(out), out)

    def test_audit_english(self):
        i18n.set_lang("en")
        config = ROOT / "tests/fixtures/cve/claude_desktop_config.json"
        text = render(build(skills=ROOT / "ejemplos", config=config, check_fn=lambda pkgs: []))
        self.assertIn("# AI Agent Security Audit (AgentGuard)", text)
        self.assertIn("How to fix:", text)
        self.assertIsNone(SPANISH.search(text), text)
        # la lógica interna no cambia con el idioma
        i18n.set_lang("es")
        es = build(skills=ROOT / "ejemplos", config=config, check_fn=lambda pkgs: [])
        i18n.set_lang("en")
        en = build(skills=ROOT / "ejemplos", config=config, check_fn=lambda pkgs: [])
        self.assertEqual([i.severidad for i in es.items], [i.severidad for i in en.items])


if __name__ == "__main__":
    unittest.main()
