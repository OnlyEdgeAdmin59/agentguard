"""agentguard tokens: credenciales vencidas, por vencer o en texto plano. Sin red.
Los tokens de prueba se arman en el momento (falsos) para que no parezcan secretos reales en el repo.
Correr: python -m unittest discover tests
"""
import base64
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import agentguard  # noqa: E402
from agentguard.audit import build, render  # noqa: E402
from agentguard.i18n import set_lang  # noqa: E402
from agentguard.tokens import check_server, cmd_tokens, mask  # noqa: E402

CERT = ROOT / "tests" / "fixtures" / "tokens" / "ca.pem"  # autofirmado de prueba, vence 2036-11-15
NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def jwt(exp=None):
    payload = {"sub": "test"} | ({"exp": exp} if exp is not None else {})
    return f"{b64({'alg': 'HS256', 'typ': 'JWT'})}.{b64(payload)}.firmafalsa"


GH = "gh" + "p_" + "A1b2C3d4" * 5          # formato de token GitHub, falso
FC = "f" + "c-" + "0123456789abcdef" * 2   # formato Firecrawl, falso


def kinds(findings):
    return [(f.level, f.kind) for f in findings]


class Reglas(unittest.TestCase):
    def check(self, server, now=NOW):
        return check_server("Cursor", "srv", server, ROOT, now)

    def test_jwt_vencido_por_vencer_sin_exp(self):
        vencido = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp())
        pronto = int(datetime(2026, 11, 25, tzinfo=timezone.utc).timestamp())
        f = self.check({"headers": {"Authorization": f"Bearer {jwt(vencido)}"}})
        self.assertIn(("ALTO", "token vencido"), kinds(f))
        self.assertIn(("MEDIO", "secreto en texto plano"), kinds(f))
        self.assertIn(("MEDIO", "token por vencer"), kinds(self.check({"env": {"API_TOKEN": jwt(pronto)}})))
        self.assertIn(("INFO", "token sin vencimiento"), kinds(self.check({"env": {"API_TOKEN": jwt()}})))
        lejos = int(datetime(2027, 6, 1, tzinfo=timezone.utc).timestamp())
        self.assertEqual(kinds(self.check({"env": {"X": jwt(lejos)}})), [("MEDIO", "secreto en texto plano")])

    def test_claves_conocidas_y_literales(self):
        f = self.check({"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": GH, "FIRECRAWL_API_KEY": FC,
                                "DB_PASSWORD": "s3cr3t-larga-123"}, "args": ["--token", GH]})
        self.assertEqual(len(f), 4)
        self.assertTrue(all(k == ("MEDIO", "secreto en texto plano") for k in kinds(f)))
        self.assertEqual({dict(x.values).get("type") for x in f}, {"GitHub", "Firecrawl", None})

    def test_nunca_muestra_el_secreto(self):
        f = self.check({"env": {"GITHUB_TOKEN": GH}})
        text = json.dumps([x.detail.format(**dict(x.values)) for x in f], ensure_ascii=False)
        self.assertNotIn(GH, text)
        self.assertIn(mask(GH), text)
        self.assertEqual(mask(GH), f"{GH[:4]}…[{len(GH)}]")

    def test_referencias_y_marcadores_no_cuentan(self):
        f = self.check({"env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}", "API_KEY": "${env:API_KEY}",
                                "OTHER_KEY": "$OTHER", "WIN_KEY": "%WIN_KEY%", "TOKEN": "<tu-token-aqui>",
                                "SLACK_TOKEN": "your-token-here", "DEBUG": "true-or-false-flag",
                                "LOG_LEVEL": "verbose-everything", "AUTH_MODE": "oauth-device-flow",
                                "TOKEN_LIMIT": "1000000000000", "AUTH_URL": "https://login.example.com/oauth2",
                                "API_KEY_PATH": "C:\\Users\\x\\keys\\k1.json"}})
        self.assertEqual(f, [])

    def test_url_con_clave(self):
        f = self.check({"url": "https://mcp.example.com/sse?api_key=abcdef1234567890"})
        self.assertEqual(kinds(f), [("MEDIO", "secreto en texto plano")])
        self.assertEqual(self.check({"url": "https://mcp.example.com/sse?page=2"}), [])

    def test_certificados(self):
        srv = {"env": {"NODE_EXTRA_CA_CERTS": str(CERT)}}
        self.assertEqual(self.check(srv), [])
        self.assertEqual(kinds(self.check(srv, datetime(2037, 1, 1, tzinfo=timezone.utc))),
                         [("ALTO", "certificado vencido")])
        self.assertEqual(kinds(self.check(srv, datetime(2036, 11, 1, tzinfo=timezone.utc))),
                         [("MEDIO", "certificado por vencer")])
        self.assertEqual(kinds(self.check({"args": ["--ca", "no/existe.pem"]})),
                         [("MEDIO", "certificado no encontrado")])
        rel = self.check({"env": {"SSL_CERT_FILE": "tests/fixtures/tokens/ca.pem"}})  # relativo a la config
        self.assertEqual(rel, [])


def write_cfg(tmp, servers):
    cfg = Path(tmp) / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
    return cfg


def run(fn, *a, **kw):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(*a, **kw)
    return code, buf.getvalue()


class Comando(unittest.TestCase):
    def test_codigo_y_salida(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = write_cfg(tmp, {"gh": {"command": "npx", "args": ["x@1.0.0"], "env": {"GITHUB_TOKEN": GH}},
                                  "ok": {"command": "npx", "args": ["y@1.0.0"], "env": {"K": "${K}"}}})
            code, out = run(cmd_tokens, [str(cfg)], now=NOW)
            self.assertEqual(code, 1)
            self.assertIn("[MEDIO] secreto en texto plano — archivo · gh · env.GITHUB_TOKEN: token GitHub", out)
            self.assertNotIn(GH, out)
            self.assertIn("No se usó la red", out)
            limpio = write_cfg(tmp, {"ok": {"command": "npx", "args": ["y@1.0.0"], "env": {"K": "${K}"}}})
            code, out = run(cmd_tokens, [str(limpio)], now=NOW)
            self.assertEqual(code, 0)
            self.assertIn("(sin credenciales vencidas", out)

    def test_main_ingles_y_warn_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = write_cfg(tmp, {"fc": {"command": "npx", "args": ["firecrawl-mcp"], "env": {"FIRECRAWL_API_KEY": FC}}})
            try:
                code, out = run(agentguard.main, ["agentguard", "--lang", "en", "tokens", str(cfg)])
            finally:
                set_lang("es")
            self.assertEqual(code, 1)
            self.assertIn("[MEDIUM] plaintext secret — file · fc · env.FIRECRAWL_API_KEY: Firecrawl token", out)
            code, _ = run(agentguard.main, ["agentguard", "--warn-only", "tokens", str(cfg)])
            self.assertEqual(code, 0)

    def test_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = write_cfg(tmp, {"gh": {"command": "docker", "args": ["run", "x"], "env": {"GITHUB_TOKEN": GH}}})
            text = render(build(config=cfg, check_fn=None))
            self.assertIn("**tokens**: 1 credencial(es)", text)
            self.assertIn("variable de entorno", text)
            self.assertNotIn(GH, text)


if __name__ == "__main__":
    unittest.main()
