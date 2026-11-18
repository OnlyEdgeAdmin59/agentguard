"""Estado en el registro (npm / PyPI): obsoleto, retirado, inexistente, abandonado. Sin red.
Correr: python -m unittest discover tests
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import agentguard  # noqa: E402
from agentguard.audit import build, render  # noqa: E402
from agentguard.cve import cmd_cve, status  # noqa: E402
from agentguard.cve.inventory import Package  # noqa: E402
from agentguard.cve.status import ABANDONADO, INEXISTENTE, OBSOLETO, RETIRADA, check_status, npm_url  # noqa: E402
from agentguard.i18n import set_lang  # noqa: E402

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)
ARCHIVED = "Archived and unmaintained; no security guarantees. See https://github.com/modelcontextprotocol/servers-archived"

# Formas reales de registry.npmjs.org y pypi.org/pypi/<pkg>/json, recortadas.
REGISTRY = {
    npm_url("@modelcontextprotocol/server-github"): {
        "dist-tags": {"latest": "2025.4.8"},
        "versions": {"2025.4.8": {"deprecated": ARCHIVED}, "0.6.2": {"deprecated": ARCHIVED}},
        "time": {"2025.4.8": "2025-04-08T10:08:59.978Z", "0.6.2": "2024-12-01T00:00:00.000Z"},
    },
    npm_url("@modelcontextprotocol/server-filesystem"): {
        "dist-tags": {"latest": "2.4.0"},
        "versions": {"2025.1.14": {"deprecated": "Use 2.x"}, "2.4.0": {}},
        "time": {"2025.1.14": "2025-01-14T00:00:00Z", "2.4.0": "2026-11-18T09:19:39.880Z"},
    },
    npm_url("mcp-viejo"): {
        "dist-tags": {"latest": "1.0.0"}, "versions": {"1.0.0": {}},
        "time": {"created": "2023-01-01T00:00:00Z", "modified": "2026-10-01T00:00:00Z", "1.0.0": "2023-01-02T00:00:00Z"},
    },
    npm_url("mcp-remote"): {
        "dist-tags": {"latest": "0.1.40"}, "versions": {"0.1.15": {}, "0.1.40": {}},
        "time": {"0.1.15": "2025-06-01T00:00:00Z", "0.1.40": "2026-10-01T00:00:00Z"},
    },
    "https://pypi.org/pypi/mcp-server-git/json": {
        "info": {"classifiers": ["Development Status :: 4 - Beta"]},
        "releases": {"0.6.2": [{"yanked": True, "yanked_reason": "path traversal",
                                "upload_time_iso_8601": "2025-01-01T00:00:00Z"}],
                     "2026.11.18": [{"yanked": False, "upload_time_iso_8601": "2026-11-18T09:15:43Z"}]},
    },
    "https://pypi.org/pypi/mcp-inactivo/json": {
        "info": {"classifiers": ["Development Status :: 7 - Inactive"]},
        "releases": {"1.0": [{"yanked": False, "upload_time_iso_8601": "2026-01-01T00:00:00Z"}]},
    },
}


class FakeRegistry:
    def __init__(self):
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return REGISTRY.get(url)  # None = 404


def kinds(statuses):
    return {(s.package.name, s.kind) for s in statuses}


class Estado(unittest.TestCase):
    def check(self, *pkgs):
        fake = FakeRegistry()
        return check_status(pkgs, get=fake.get, now=NOW), fake

    def test_archivado_sin_cve(self):
        (st,), _ = self.check(Package("@modelcontextprotocol/server-github", "npm", None))
        self.assertEqual(st.kind, OBSOLETO)
        self.assertIn("Archived and unmaintained", st.detail)
        self.assertNotIn("actualizar", st.detail)  # la última también está archivada

    def test_version_vieja_obsoleta_sugiere_actualizar(self):
        (st,), _ = self.check(Package("@modelcontextprotocol/server-filesystem", "npm", "2025.1.14"))
        self.assertEqual(st.kind, OBSOLETO)
        self.assertIn("actualizar a 2.4.0", st.detail)

    def test_activo_sin_avisos(self):
        statuses, _ = self.check(Package("@modelcontextprotocol/server-filesystem", "npm", "2.4.0"),
                                 Package("mcp-remote", "npm", "0.1.15"))
        self.assertEqual(statuses, [])

    def test_inexistente(self):
        statuses, _ = self.check(Package("mcp-inventado-por-la-ia", "npm", None),
                                 Package("mcp-remote", "npm", "9.9.9"),
                                 Package("mcp-server-inventado", "PyPI", "1.0"))
        self.assertEqual(kinds(statuses), {("mcp-inventado-por-la-ia", INEXISTENTE), ("mcp-remote", INEXISTENTE),
                                           ("mcp-server-inventado", INEXISTENTE)})

    def test_abandonado_mira_versiones_no_modified(self):
        (st,), _ = self.check(Package("mcp-viejo", "npm", "1.0.0"))
        self.assertEqual(st.kind, ABANDONADO)
        self.assertIn("46 meses", st.detail)

    def test_pypi_yanked_e_inactivo(self):
        statuses, _ = self.check(Package("mcp-server-git", "PyPI", "0.6.2"), Package("mcp-inactivo", "PyPI", None))
        self.assertEqual(kinds(statuses), {("mcp-server-git", RETIRADA), ("mcp-inactivo", OBSOLETO)})
        self.assertIn("path traversal", next(s.detail for s in statuses if s.kind == RETIRADA))

    def test_solo_pide_el_nombre_y_una_vez(self):
        _, fake = self.check(Package("mcp-remote", "npm", "0.1.15"), Package("mcp-remote", "npm", "0.1.40"),
                             Package("@modelcontextprotocol/server-github", "npm", None))
        self.assertEqual(sorted(fake.urls), ["https://registry.npmjs.org/@modelcontextprotocol%2Fserver-github",
                                             "https://registry.npmjs.org/mcp-remote"])


FIX = ROOT / "tests" / "fixtures" / "cve"


def run(fn, *args, **kw):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(*args, **kw)
    return code, buf.getvalue()


def fake_status(pkgs):
    return check_status(pkgs, get=FakeRegistry().get, now=NOW)


class Comando(unittest.TestCase):
    CFG = str(FIX / "claude_desktop_config.json")

    def test_obsoleto_hace_fallar_sin_cves(self):
        code, out = run(cmd_cve, [self.CFG], check_fn=lambda p: [], status_fn=fake_status)
        self.assertEqual(code, 1)
        self.assertIn("Estado en el registro", out)
        self.assertIn("[ALTO] @modelcontextprotocol/server-filesystem 2025.1.14 (npm): obsoleto", out)

    def test_sin_estado(self):
        def boom(_):
            raise AssertionError("no debía consultar el registro")
        code, out = run(cmd_cve, [self.CFG, "--sin-estado"], check_fn=lambda p: [], status_fn=boom)
        self.assertEqual(code, 0)
        self.assertNotIn("Estado en el registro", out)

    def test_registro_caido_no_tumba(self):
        def down(_):
            raise OSError("sin conexión")
        code, out = run(cmd_cve, [self.CFG], check_fn=lambda p: [], status_fn=down)
        self.assertEqual(code, 0)
        self.assertIn("No se pudo consultar el estado", out)

    def test_ingles(self):
        set_lang("en")
        try:
            _, out = run(cmd_cve, [self.CFG], check_fn=lambda p: [], status_fn=fake_status)
        finally:
            set_lang("es")
        self.assertIn("deprecated — Use 2.x — update to 2.4.0", out)
        self.assertIn("Registry status", out)

    def test_audit(self):
        audit = build(config=FIX / "claude_desktop_config.json", check_fn=lambda p: [], status_fn=fake_status)
        text = render(audit)
        self.assertIn("server-filesystem 2025.1.14: obsoleto", text)
        self.assertIn("**estado**: 4 paquete(s)", text)  # el registro falso no tiene los demás: "no existe"


class WarnOnly(unittest.TestCase):
    def test_hallazgos_salen_con_0(self):
        ejemplos = str(ROOT / "ejemplos")
        self.assertEqual(run(agentguard.main, ["agentguard", "scan", ejemplos])[0], 1)
        code, out = run(agentguard.main, ["agentguard", "--warn-only", "scan", ejemplos])
        self.assertEqual(code, 0)
        self.assertIn("[ALTO]", out)
        self.assertIn("--warn-only", out)

    def test_errores_de_uso_siguen_en_2(self):
        self.assertEqual(run(agentguard.main, ["agentguard", "--warn-only", "nada", "x", "y"])[0], 2)


if __name__ == "__main__":
    unittest.main()
