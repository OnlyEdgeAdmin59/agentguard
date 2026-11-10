"""Reporte de auditoría (scan + cve + trifecta), sin red: OSV simulado con fixtures.
Correr: python -m unittest discover tests
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import agentguard  # noqa: E402
from agentguard.audit import FIX_DEFAULT, build, cmd_audit, fix_for, render  # noqa: E402
from agentguard.scanner import RULES  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from auditoria_ejemplo import offline_check  # noqa: E402

CONFIG = ROOT / "tests" / "fixtures" / "cve" / "claude_desktop_config.json"
SKILLS = ROOT / "ejemplos"


def quiet(fn, *args, **kw):
    buf = io.StringIO()
    with redirect_stdout(buf):
        return fn(*args, **kw), buf.getvalue()


class Construccion(unittest.TestCase):
    def setUp(self):
        self.audit = build(skills=SKILLS, config=CONFIG, check_fn=offline_check)
        self.by_origin = lambda o: [i for i in self.audit.items if i.origen == o]

    def test_scan(self):
        scan = self.by_origin("scan")
        self.assertTrue(any(i.severidad == "Alto" for i in scan))
        self.assertTrue(all(i.arreglo for i in scan))
        self.assertTrue(all("malicioso_tools.json" in i.donde for i in scan if i.severidad == "Alto"))
        medios = [i.titulo for i in scan if i.severidad == "Medio"]
        self.assertEqual(len(medios), len(set(medios)))  # un item por regla MEDIO
        secrets = next(i for i in scan if i.titulo == "Menciona secretos")
        self.assertEqual((secrets.donde, secrets.detalle[:7]), ("varios", "2 veces"))

    def test_cve_critico_con_arreglo(self):
        crit = [i for i in self.by_origin("cve") if i.severidad == "Crítico"]
        self.assertEqual(len(crit), 1)
        self.assertIn("CVE-2025-6514", crit[0].titulo)
        self.assertIn("0.1.16", crit[0].arreglo)
        self.assertTrue(any("no fijada" in i.titulo and "Fija la versión" in i.arreglo for i in self.by_origin("cve")))

    def test_trifecta(self):
        tri = self.by_origin("trifecta")
        self.assertEqual([i.severidad for i in tri], ["Alto"])
        self.assertIn("Quita una de estas opciones", tri[0].arreglo)

    def test_todas_las_reglas_tienen_arreglo(self):
        for _, name, _ in RULES:
            self.assertNotEqual(fix_for(name), FIX_DEFAULT, name)
        self.assertIn("dónde poner la llave", fix_for("Menciona secretos"))
        self.assertIn("cambia las llaves", fix_for("Secreto + envío externo (posible robo)"))


class Markdown(unittest.TestCase):
    def test_secciones_y_orden(self):
        text = render(build(skills=SKILLS, config=CONFIG, check_fn=offline_check), date(2026, 11, 2))
        for section in ("## Resumen ejecutivo", "**Riesgo general: Alto.**", "## Hallazgos por severidad",
                        "Cómo arreglar:", "## Revisión manual", "## Límites", "31 de 34 (91%)"):
            self.assertIn(section, text)
        self.assertLess(text.index("### Crítico"), text.index("### Alto"))
        self.assertLess(text.index("### Alto"), text.index("### Info"))
        manual = text.split("## Revisión manual")[1].split("## Límites")[0]
        self.assertIn("- [ ] Conclusión:\n", manual)  # vacía para completar a mano

    def test_sin_red_no_consulta(self):
        audit = build(config=CONFIG, check_fn=None)
        self.assertTrue(any("no se consultó" in r for r in audit.resumen))
        self.assertFalse(any(i.origen == "cve" and i.severidad == "Crítico" for i in audit.items))

    def test_osv_caido_no_rompe(self):
        def down(_):
            raise OSError("sin red")
        audit = build(config=CONFIG, check_fn=down)
        self.assertTrue(any(i.titulo == "No se pudo consultar OSV.dev" for i in audit.items))

    def test_limpio_riesgo_bajo(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "mcp.json"
            cfg.write_text(json.dumps({"mcpServers": {"hora": {"command": "uvx", "args": ["mcp-server-time==0.6.2"]}}}),
                           encoding="utf-8")
            text = render(build(config=cfg, check_fn=lambda p: []))
        self.assertIn("**Riesgo general: Bajo.**", text)
        self.assertIn("Sin hallazgos.", text)


class Comando(unittest.TestCase):
    def test_out_y_codigo(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "a.md"
            code, printed = quiet(cmd_audit, ["--skills", str(SKILLS), "--config", str(CONFIG), "--out", str(out)],
                                  check_fn=offline_check)
            self.assertEqual(code, 1)
            self.assertIn("Reporte guardado", printed)
            self.assertIn("## Revisión manual", out.read_text(encoding="utf-8"))

    def test_main_enruta_audit_y_opcion_mala(self):
        code, _ = quiet(agentguard.main, ["agentguard", "audit", "--config", str(CONFIG), "--sin-red"])
        self.assertEqual(code, 1)  # la config de ejemplo tiene tríada
        code, _ = quiet(agentguard.main, ["agentguard", "audit", "--nada"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out = quiet(agentguard.main, ["agentguard", "--version"])
        self.assertEqual((code, out.strip()), (0, f"agentguard {agentguard.__version__}"))
        self.assertEqual(agentguard.__version__, "0.5.0")


if __name__ == "__main__":
    unittest.main()
