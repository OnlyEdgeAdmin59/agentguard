"""Tríada letal: datos privados + contenido no confiable + salida hacia afuera en una misma config.
Correr: python -m unittest discover tests
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import agentguard  # noqa: E402
from agentguard.trifecta import (KNOWN, analyze, classify, cmd_trifecta, groups, load_known,  # noqa: E402
                                 scopes_of, servers_of)

FIX = ROOT / "tests" / "fixtures" / "trifecta"
PRIV, UNTRUSTED, OUT = "privado", "no_confiable", "salida"


def run(args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cmd_trifecta(args)
    return code, buf.getvalue()


def caps(group, name):
    return next(s for s in group if s.name == name).caps


class Tabla(unittest.TestCase):
    def test_tabla_valida(self):
        known = load_known()
        self.assertGreaterEqual(len(known), 15)
        for entry in known:
            self.assertTrue(entry["coincide"], entry)
            self.assertTrue(set(entry["capacidades"]) <= {PRIV, UNTRUSTED, OUT}, entry)
            self.assertTrue(entry["motivo"], entry)

    def test_clasifica_por_tabla(self):
        c = classify("archivos", {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem@1.0.0"]})
        self.assertEqual(set(c), {PRIV})
        self.assertEqual(c[PRIV].origen, "tabla")

    def test_tabla_gana_a_la_heuristica(self):
        # el nombre "web-sender" sugeriría otra cosa, pero el paquete está en la tabla
        c = classify("web-sender", {"command": "npx", "args": ["@modelcontextprotocol/server-sequential-thinking"]})
        self.assertEqual(c, {})

    def test_imagen_docker_conocida(self):
        c = classify("gh", {"command": "docker", "args": ["run", "-i", "ghcr.io/github/github-mcp-server"]})
        self.assertEqual(set(c), {PRIV, UNTRUSTED, OUT})
        self.assertTrue(all(v.origen == "tabla" for v in c.values()))


class Heuristica(unittest.TestCase):
    def test_nombre_del_servidor(self):
        c = classify("avisos", {"command": "python", "args": ["webhook_notifier.py"]})
        self.assertEqual(set(c), {OUT})
        self.assertEqual(c[OUT].origen, "heurística")
        self.assertIn("webhook", c[OUT].motivo)

    def test_tools(self):
        tools = [{"name": "post_message", "description": "Posts a message to a team chat channel."}]
        c = classify("interno", {"command": "python", "args": ["server.py"]}, tools)
        self.assertIn(OUT, c)
        self.assertIn("post_message", c[OUT].motivo)

    def test_sin_pistas(self):
        self.assertEqual(classify("interno", {"command": "python", "args": ["server.py"]}), {})

    def test_variables_de_entorno(self):
        c = classify("x", {"command": "node", "args": ["index.js"], "env": {"SLACK_BOT_TOKEN": "..."}})
        self.assertIn(OUT, c)


class Analisis(unittest.TestCase):
    def test_con_triada(self):
        group = servers_of(FIX / "con_triada.json")
        result = analyze(group)
        self.assertEqual(result.estado, "triada")
        self.assertEqual(result.aporta[PRIV], ["archivos"])
        self.assertEqual(result.aporta[UNTRUSTED], ["buscador"])
        self.assertEqual(result.aporta[OUT], ["avisos"])
        self.assertEqual(sorted(map(tuple, result.quitar)), [("archivos",), ("avisos",), ("buscador",)])

    def test_sin_triada(self):
        result = analyze(servers_of(FIX / "sin_triada.json"))
        self.assertEqual(result.estado, "sin_triada")
        self.assertEqual(result.faltan, [UNTRUSTED, OUT])

    def test_ambigua(self):
        group = servers_of(FIX / "ambigua.json")
        result = analyze(group)
        self.assertEqual(result.estado, "posible")
        self.assertEqual(result.faltan, [OUT])
        self.assertEqual(result.sin_clasificar, ["interno"])

    def test_ambigua_se_resuelve_con_tools(self):
        result = analyze(servers_of(FIX / "ambigua.json", tools_dir=FIX / "tools"))
        self.assertEqual(result.estado, "triada")
        self.assertEqual(result.aporta[OUT], ["interno"])

    def test_un_solo_servidor(self):
        result = analyze(servers_of(FIX / "un_servidor.json"))
        self.assertEqual(result.estado, "triada")
        self.assertEqual(result.solo, ["github"])
        self.assertEqual(result.quitar, [["github"]])


class PorProyecto(unittest.TestCase):
    """Claude Code: cada proyecto hereda los servidores globales, pero no ve los de otros proyectos."""

    def test_juntos_hay_triada_por_separado_no(self):
        path = FIX / "claude_dos_proyectos.json"
        self.assertEqual(analyze(servers_of(path)).estado, "triada")  # mezclar todo inventa una tríada
        scopes = scopes_of(path)
        self.assertEqual(list(scopes), ["global", "proyecto /home/demo/a", "proyecto /home/demo/b"])
        for label, group in scopes.items():
            self.assertNotEqual(analyze(group).estado, "triada", label)
        self.assertEqual(sorted(s.name for s in scopes["proyecto /home/demo/a"]), ["archivos", "buscador"])

    def test_reporte_dice_el_proyecto(self):
        code, out = run([str(FIX / "claude_dos_proyectos.json")])
        self.assertEqual(code, 0)
        self.assertNotIn("TRÍADA LETAL", out)
        code, out = run([str(FIX / "claude_proyecto_con_triada.json")])
        self.assertEqual(code, 1)
        self.assertEqual(out.count("TRÍADA LETAL"), 1)
        block = out.split("== ")[[i for i, b in enumerate(out.split("== ")) if "TRÍADA LETAL" in b][0]]
        self.assertTrue(block.startswith("archivo · proyecto /home/demo/c"), block[:60])

    def test_inventario_hereda_global_y_suma_mcp_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, project = Path(tmp) / "home", Path(tmp) / "proyecto"
            home.mkdir()
            project.mkdir()
            data = json.loads((FIX / "claude_dos_proyectos.json").read_text(encoding="utf-8"))
            data["projects"] = {str(project): data["projects"]["/home/demo/a"], "/otro": data["projects"]["/home/demo/b"]}
            (home / ".claude.json").write_text(json.dumps(data), encoding="utf-8")
            avisos = {"mcpServers": {"avisos2": {"command": "python", "args": ["webhook_notifier.py"]}}}
            (project / ".mcp.json").write_text(json.dumps(avisos), encoding="utf-8")
            found = groups(project, system="linux", home=home, env={})
        self.assertEqual(list(found), ["Claude Code · global", "Claude Code · proyecto /otro",
                                       f"Claude Code · proyecto {project}"])
        self.assertEqual(analyze(found["Claude Code · proyecto /otro"]).estado, "sin_triada")
        target = found[f"Claude Code · proyecto {project}"]
        self.assertEqual(sorted(s.name for s in target), ["archivos", "avisos2", "buscador"])
        self.assertEqual(analyze(target).estado, "triada")


class Comando(unittest.TestCase):
    def test_aviso_explica_y_sale_1(self):
        code, out = run([str(FIX / "con_triada.json")])
        self.assertEqual(code, 1)
        self.assertIn("TRÍADA LETAL", out)
        self.assertIn("archivos", out)
        self.assertIn("(tabla", out)
        self.assertIn("(heurística", out)
        self.assertIn("Para romperla", out)

    def test_sin_triada_sale_0(self):
        code, out = run([str(FIX / "sin_triada.json")])
        self.assertEqual(code, 0)
        self.assertIn("Sin tríada", out)

    def test_ambigua_avisa_sin_fallar(self):
        code, out = run([str(FIX / "ambigua.json")])
        self.assertEqual(code, 0)
        self.assertIn("POSIBLE", out)
        self.assertIn("interno", out)
        code, out = run([str(FIX / "ambigua.json"), "--tools", str(FIX / "tools")])
        self.assertEqual(code, 1)

    def test_main_enruta_trifecta(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = agentguard.main(["agentguard", "trifecta", str(FIX / "sin_triada.json")])
        self.assertEqual(code, 0)

    def test_known_se_carga_del_paquete(self):
        self.assertTrue(KNOWN.is_file())
        self.assertEqual(KNOWN.parent.name, "trifecta")


if __name__ == "__main__":
    unittest.main()
