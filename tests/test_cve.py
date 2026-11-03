"""Módulo CVE: inventario de configs MCP y consulta a OSV simulada (sin red).
Correr: python -m unittest discover tests
"""
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import agentguard  # noqa: E402
from agentguard.cve import cmd_cve, inventory, servers_from_file  # noqa: E402
from agentguard.cve import osv  # noqa: E402
from agentguard.cve.inventory import Package, package_of, parse_npm_spec, parse_pypi_spec, strip_jsonc  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "cve"


def by_name(servers):
    return {s.name: s for s in servers}


class FakeOSV:
    """Responde como OSV con los fixtures y guarda todo lo que se habría enviado."""

    def __init__(self):
        self.posts, self.gets = [], []

    VULNS = {"mcp-remote": "GHSA-6xpm-ggf7-wc3p", "mcp-server-git": "PYSEC-2025-0001"}

    def post(self, url, payload):
        self.posts.append((url, payload))
        return {"results": [{"vulns": [{"id": self.VULNS[q["package"]["name"]]}]}
                            if q["package"]["name"] in self.VULNS else {} for q in payload["queries"]]}

    def get(self, url):
        self.gets.append(url)
        return json.loads((FIX / "osv" / f"{url.rsplit('/', 1)[1]}.json").read_text(encoding="utf-8"))


class Specs(unittest.TestCase):
    def test_npm(self):
        self.assertEqual(parse_npm_spec("@scope/pkg@1.2.3"), Package("@scope/pkg", "npm", "1.2.3"))
        self.assertEqual(parse_npm_spec("pkg@v2.0.0-beta.1"), Package("pkg", "npm", "2.0.0-beta.1"))
        self.assertEqual(parse_npm_spec("@scope/pkg"), Package("@scope/pkg", "npm", None))
        self.assertEqual(parse_npm_spec("pkg@latest").version, None)
        self.assertEqual(parse_npm_spec("pkg@^1.2.0").version, None)

    def test_pypi(self):
        self.assertEqual(parse_pypi_spec("mcp-server-git==0.6.2"), Package("mcp-server-git", "PyPI", "0.6.2"))
        self.assertEqual(parse_pypi_spec("Some_Package[cli]==1.4.0"), Package("some-package", "PyPI", "1.4.0"))
        self.assertEqual(parse_pypi_spec("pkg@1.0"), Package("pkg", "PyPI", "1.0"))
        self.assertEqual(parse_pypi_spec("pkg>=1.0").version, None)
        self.assertEqual(parse_pypi_spec("pkg").version, None)

    def test_comandos_sin_paquete(self):
        self.assertIsNone(package_of({"command": "docker", "args": ["run", "x"]})[0])
        self.assertIsNone(package_of({"command": "python", "args": ["server.py"]})[0])
        self.assertIsNone(package_of({"url": "https://x.dev/mcp"})[0])
        self.assertIsNone(package_of({"command": "npx", "args": ["-y"]})[0])

    def test_jsonc_respeta_strings(self):
        data = json.loads(strip_jsonc('{"a": "http://x//y", /* c */ "b": [1,], // fin\n}'))
        self.assertEqual(data, {"a": "http://x//y", "b": [1]})


class Configs(unittest.TestCase):
    def test_claude_desktop(self):
        s = by_name(servers_from_file("Claude Desktop", FIX / "claude_desktop_config.json"))
        self.assertEqual(s["filesystem"].package, Package("@modelcontextprotocol/server-filesystem", "npm", "2025.1.14"))
        self.assertEqual(s["remote-ok"].package, Package("mcp-remote", "npm", "0.1.15"))
        self.assertEqual(s["git"].package, Package("mcp-server-git", "PyPI", "0.6.2"))
        self.assertEqual(s["fetch"].package, Package("mcp-server-fetch", "PyPI", None))
        self.assertIn("no fijada", s["fetch"].note)
        self.assertEqual(s["win-wrapped"].package, Package("@playwright/mcp", "npm", "0.0.29"))
        self.assertIsNone(s["docker"].package)

    def test_claude_code_con_proyectos(self):
        s = by_name(servers_from_file("Claude Code", FIX / "claude.json"))
        self.assertEqual(s["context7"].package.version, None)
        self.assertIsNone(s["sentry"].package)
        self.assertEqual(s["time"].package, Package("mcp-server-time", "PyPI", "0.6.2"))

    def test_cursor_package_flag(self):
        s = by_name(servers_from_file("Cursor", FIX / "cursor_mcp.json"))
        self.assertEqual(s["pkg-flag"].package, Package("@modelcontextprotocol/sdk", "npm", "1.10.0"))

    def test_vscode(self):
        mcp = by_name(servers_from_file("VS Code", FIX / "vscode_mcp.json"))
        self.assertEqual(mcp["pipx-tool"].package, Package("some-package", "PyPI", "1.4.0"))
        settings = by_name(servers_from_file("VS Code", FIX / "vscode_settings.json"))
        self.assertEqual(settings["memory"].package, Package("@modelcontextprotocol/server-memory", "npm", "0.6.0"))

    def test_json_invalido_no_rompe(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "mcp.json"
            bad.write_text("{ no es json", encoding="utf-8")
            self.assertEqual(servers_from_file("Cursor", bad)[0].note, "JSON inválido")


class RutasPorSistema(unittest.TestCase):
    LAYOUT = {
        "win32": {"Claude Desktop": "AppData/Roaming/Claude/claude_desktop_config.json",
                  "VS Code": "AppData/Roaming/Code/User/mcp.json"},
        "darwin": {"Claude Desktop": "Library/Application Support/Claude/claude_desktop_config.json",
                   "VS Code": "Library/Application Support/Code/User/mcp.json"},
        "linux": {"Claude Desktop": ".config/Claude/claude_desktop_config.json",
                  "VS Code": ".config/Code/User/mcp.json"},
    }

    def test_encuentra_configs_en_cada_sistema(self):
        for system, layout in self.LAYOUT.items():
            with self.subTest(system=system), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp) / "home"
                project = Path(tmp) / "proj"
                files = {**layout, "Cursor": ".cursor/mcp.json", "Claude Code": ".claude.json"}
                src = {"Claude Desktop": "claude_desktop_config.json", "VS Code": "vscode_mcp.json",
                       "Cursor": "cursor_mcp.json", "Claude Code": "claude.json"}
                for client, rel in files.items():
                    (home / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(FIX / src[client], home / rel)
                (project / ".vscode").mkdir(parents=True)
                shutil.copy(FIX / "vscode_settings.json", project / ".vscode" / "mcp.json")
                env = {"APPDATA": str(home / "AppData" / "Roaming")} if system == "win32" else {}
                servers = inventory(project=project, system=system, home=home, env=env)
                clients = {s.client for s in servers}
                self.assertEqual(clients, {"Claude Desktop", "Claude Code", "Cursor", "VS Code"})
                self.assertIn("memory", by_name(servers))  # .vscode/mcp.json del proyecto


class OSV(unittest.TestCase):
    PKGS = [Package("@modelcontextprotocol/server-filesystem", "npm", "2025.1.14"),
            Package("mcp-remote", "npm", "0.1.15"),
            Package("mcp-server-git", "PyPI", "0.6.2"),
            Package("mcp-server-fetch", "PyPI", None)]

    def test_solo_envia_nombre_ecosistema_version(self):
        fake = FakeOSV()
        osv.check(self.PKGS, post=fake.post, get=fake.get)
        (url, payload), = fake.posts
        self.assertEqual(url, "https://api.osv.dev/v1/querybatch")
        self.assertEqual(set(payload), {"queries"})
        self.assertEqual(len(payload["queries"]), 3)  # el de versión no fijada no se consulta
        for q in payload["queries"]:
            self.assertEqual(set(q), {"package", "version"})
            self.assertEqual(set(q["package"]), {"name", "ecosystem"})
        enviado = json.dumps(payload)
        for prohibido in ("description", "Documents", "args", "command", "mcp-server-fetch"):
            self.assertNotIn(prohibido, enviado)
        self.assertTrue(all(u.startswith("https://api.osv.dev/v1/vulns/") for u in fake.gets))

    def test_resultado(self):
        fake = FakeOSV()
        vulns = {v.package.name: v for v in osv.check(self.PKGS, post=fake.post, get=fake.get)}
        self.assertEqual(set(vulns), {"mcp-remote", "mcp-server-git"})
        v = vulns["mcp-remote"]
        self.assertEqual((v.cve, v.severity, v.fixed), ("CVE-2025-6514", "CRITICAL", "0.1.16"))
        g = vulns["mcp-server-git"]
        self.assertEqual((g.cve, g.severity, g.fixed), ("PYSEC-2025-0001", "desconocida", "0.6.3"))

    def test_paginacion(self):
        calls = []

        def post(url, payload):
            calls.append(payload)
            if len(calls) == 1:
                return {"results": [{"vulns": [{"id": "A"}], "next_page_token": "t1"}]}
            self.assertEqual(payload["queries"][0]["page_token"], "t1")
            return {"results": [{"vulns": [{"id": "B"}]}]}

        ids = osv.batch_ids([Package("x", "npm", "1.0.0")], post=post)
        self.assertEqual(ids[Package("x", "npm", "1.0.0")], ["A", "B"])

    def test_sin_versiones_no_llama(self):
        def boom(*_):
            raise AssertionError("no debía llamar a la red")
        self.assertEqual(osv.check([Package("x", "npm", None)], post=boom, get=boom), [])


class Comando(unittest.TestCase):
    def run_cli(self, args, check_fn):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cmd_cve(args, check_fn=check_fn)
        return code, buf.getvalue()

    def test_tabla_y_codigo_1(self):
        fake = FakeOSV()
        code, out = self.run_cli([str(FIX / "claude_desktop_config.json")],
                                 lambda pkgs: osv.check(pkgs, post=fake.post, get=fake.get))
        self.assertEqual(code, 1)
        self.assertIn("CVE-2025-6514", out)
        self.assertIn("CRITICAL", out)
        self.assertIn("0.1.16", out)
        self.assertIn("versión no fijada", out)

    def test_sin_red(self):
        def offline(_):
            raise OSError("sin conexión")
        code, out = self.run_cli([str(FIX / "claude_desktop_config.json")], offline)
        self.assertEqual(code, 2)
        self.assertIn("No se pudo consultar OSV.dev", out)

    def test_main_enruta_cve(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "mcp.json"
            empty.write_text("{}", encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agentguard.main(["agentguard", "cve", str(empty)])
        self.assertEqual(code, 0)
        self.assertIn("No se encontraron servidores MCP", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
