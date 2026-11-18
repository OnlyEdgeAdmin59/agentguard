"""agentguard tokens: credenciales vencidas, por vencer o en texto plano en las configs MCP.

Lección del caso DHS (un certificado vencido dejó al personal sin sistemas): una credencial
vencida tumba el servidor MCP sin aviso, y una clave escrita en el JSON se filtra con
cualquier copia, backup o captura del archivo.

Revisa env, headers, args y url de cada servidor:
- JWT (eyJ…): lee `exp` sin verificar la firma. Vencido → ALTO; vence pronto → MEDIO; sin `exp` → INFO.
- Certificados (.pem/.crt/.cer o variables como NODE_EXTRA_CA_CERTS): lee `notAfter` del primero.
- Claves con formato conocido (ghp_, sk-ant-, xoxb-, AKIA…) o variables *TOKEN/*KEY/*SECRET con valor
  literal → MEDIO "en texto plano".
Todo local: no usa la red. Nunca muestra el secreto, solo dónde está, su tipo y el largo.
"""
from __future__ import annotations

import base64
import json
import os
import re
import ssl
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .cve.inventory import config_paths, servers_in, strip_jsonc
from .i18n import t

SOON_DAYS = 14

JWT = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")
# (tipo, patrón). Orden: lo más específico primero.
KNOWN = [
    ("GitHub", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("GitLab", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")),
    ("Anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("Slack", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("AWS", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Google", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    ("Notion", re.compile(r"\b(?:ntn_|secret_)[A-Za-z0-9]{30,}")),
    ("Linear", re.compile(r"\blin_api_[A-Za-z0-9]{30,}")),
    ("Firecrawl", re.compile(r"\bfc-[A-Za-z0-9]{24,}")),
    ("Stripe", re.compile(r"\b[rs]k_live_[A-Za-z0-9]{20,}")),
]
SECRET_NAME = re.compile(r"(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|_PAT$|^PAT$|AUTH)", re.I)
CERT_NAME = re.compile(r"(NODE_EXTRA_CA_CERTS|SSL_CERT_FILE|REQUESTS_CA_BUNDLE|CURL_CA_BUNDLE|_CERT(_FILE|_PATH)?$|_CA$)", re.I)
REFERENCE = re.compile(r"^\s*(\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%)\s*$")
NOT_SECRET_NAME = re.compile(r"(_URL|_URI|_HOST|_MODE|_LIMIT|_DIR|_PATH|_TYPE|_NAME|_ID|_ENDPOINT|_SCOPES?|_TTL|_TIMEOUT)$", re.I)
PLACEHOLDER = re.compile(r"^(<.*>|x+|\*+|your[-_ ].*|tu[-_ ].*|changeme|example.*|\.\.\.|todo|none|null|true|false)$", re.I)


@dataclass(frozen=True)
class TokenFinding:
    level: str      # ALTO / MEDIO / INFO
    kind: str       # plantilla corta (clave de i18n)
    where: str      # cliente · servidor · campo
    detail: str     # plantilla (clave de i18n)
    values: tuple = ()


def looks_secret(value: str) -> bool:
    """Valor literal con pinta de clave: largo, letras y números, no URL ni ruta."""
    v = value.strip()
    if len(v) < 12 or " " in v or "://" in v or v.startswith(("/", "~", ".")) or re.match(r"^[A-Za-z]:[\\/]", v):
        return False
    return bool(re.search(r"[A-Za-z]", v) and re.search(r"\d", v)) and not PLACEHOLDER.match(v)


def mask(secret: str) -> str:
    return f"{secret[:4]}…[{len(secret)}]"


def b64json(part: str) -> dict | None:
    try:
        data = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def days_left(when: datetime, now: datetime) -> int:
    return int((when - now).total_seconds() // 86400)


def check_jwt(token: str, where: str, now: datetime, soon: int) -> TokenFinding | None:
    header, payload = (b64json(p) for p in token.split(".")[:2])
    if header is None or payload is None:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return TokenFinding("INFO", "token sin vencimiento", where,
                            "JWT sin fecha de vencimiento (exp): si se filtra, sirve para siempre")
    when = datetime.fromtimestamp(exp, timezone.utc)
    left = days_left(when, now)
    if left < 0:
        return TokenFinding("ALTO", "token vencido", where, "JWT vencido el {date}: el servidor va a fallar",
                            (("date", when.date().isoformat()),))
    if left <= soon:
        return TokenFinding("MEDIO", "token por vencer", where, "JWT vence el {date} (en {days} día(s))",
                            (("date", when.date().isoformat()), ("days", left)))
    return None


def cert_not_after(path: Path) -> datetime | None:
    """notAfter del primer certificado PEM del archivo (sin dependencias)."""
    try:
        info = ssl._ssl._test_decode_cert(str(path))  # noqa: SLF001 (CPython: lee el primer cert del PEM)
        return datetime.strptime(info["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except (OSError, ValueError, KeyError, AttributeError, ssl.SSLError):
        return None


def check_cert(value: str, where: str, base: Path, now: datetime, soon: int) -> TokenFinding | None:
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    if not path.is_absolute():
        path = base / path
    if not path.is_file():
        return TokenFinding("MEDIO", "certificado no encontrado", where,
                            "el archivo {path} no existe: el servidor puede fallar al conectar", (("path", value),))
    when = cert_not_after(path)
    if when is None:
        return TokenFinding("INFO", "certificado no leído", where,
                            "no se pudo leer la fecha de {path} (¿no es PEM?): revísalo a mano", (("path", value),))
    left = days_left(when, now)
    if left < 0:
        return TokenFinding("ALTO", "certificado vencido", where, "{path} venció el {date}",
                            (("path", value), ("date", when.date().isoformat())))
    if left <= max(soon, 30):
        return TokenFinding("MEDIO", "certificado por vencer", where, "{path} vence el {date} (en {days} día(s))",
                            (("path", value), ("date", when.date().isoformat()), ("days", left)))
    return None


def strings_of(server: dict) -> Iterable[tuple[str, str, str]]:
    """(campo, nombre, valor) de env, headers, args y url."""
    for section in ("env", "headers"):
        block = server.get(section)
        if isinstance(block, dict):
            for k, v in block.items():
                if isinstance(v, str):
                    yield section, str(k), v
    for i, a in enumerate(server.get("args") or []):
        if isinstance(a, str):
            yield "args", str(i), a
    if isinstance(server.get("url"), str):
        yield "url", "", server["url"]


def check_server(client: str, name: str, server: dict, base: Path, now: datetime,
                 soon: int = SOON_DAYS) -> list[TokenFinding]:
    out: list[TokenFinding] = []
    for section, key, value in strings_of(server):
        where = f"{client} · {name} · {section}{'.' + key if key and section != 'args' else ''}"
        if section == "args":
            where = f"{client} · {name} · args[{key}]"
        if REFERENCE.match(value):
            continue  # ${env:X} / $X: el secreto vive fuera del archivo
        is_cert_var = section == "env" and bool(CERT_NAME.search(key))
        is_cert_path = bool(re.search(r"\.(pem|crt|cer)$", value.strip(), re.I)) and "://" not in value
        if is_cert_var or is_cert_path:
            f = check_cert(value.strip(), where, base, now, soon)
            if f:
                out.append(f)
            continue
        found = False
        for token in JWT.findall(value):
            f = check_jwt(token, where, now, soon)
            if f:
                out.append(f)
            out.append(TokenFinding("MEDIO", "secreto en texto plano", where,
                                    "token {type} escrito en el archivo: {masked}",
                                    (("type", "JWT"), ("masked", mask(token)))))
            found = True
        if found:
            continue
        for kind, rx in KNOWN:
            m = rx.search(value)
            if m:
                out.append(TokenFinding("MEDIO", "secreto en texto plano", where,
                                        "token {type} escrito en el archivo: {masked}",
                                        (("type", kind), ("masked", mask(m.group(0))))))
                found = True
                break
        if found:
            continue
        literal = value.strip().removeprefix("Bearer ").strip()
        if section in ("env", "headers") and SECRET_NAME.search(key) and not NOT_SECRET_NAME.search(key) \
                and looks_secret(literal):
            out.append(TokenFinding("MEDIO", "secreto en texto plano", where,
                                    "valor literal en {key}: {masked}", (("key", key), ("masked", mask(literal)))))
        elif section == "url" and re.search(r"[?&](api[_-]?key|token|key|access_token|auth)=[^&\s]{12,}", value, re.I):
            out.append(TokenFinding("MEDIO", "secreto en texto plano", where, "clave dentro de la URL"))
    return out


def raw_from_file(client: str, path: Path) -> list[tuple[str, str, dict, Path]]:
    try:
        data = json.loads(strip_jsonc(path.read_text(encoding="utf-8", errors="replace")))
    except (OSError, json.JSONDecodeError):
        return []
    return [(client, name, server, path.parent) for name, server in servers_in(data).items()]


def raw_inventory(project: Path | None = None, system: str | None = None, home: Path | None = None,
                  env: Mapping[str, str] | None = None) -> list[tuple[str, str, dict, Path]]:
    paths = config_paths(system or sys.platform, home or Path.home(), os.environ if env is None else env, project)
    seen: set[Path] = set()
    out = []
    for client, path in paths:
        if path.is_file() and path.resolve() not in seen:
            seen.add(path.resolve())
            out += raw_from_file(client, path)
    return out


def scan_tokens(target: Path | None = None, now: datetime | None = None, soon: int = SOON_DAYS,
                **inv) -> tuple[int, list[TokenFinding]]:
    """(servidores revisados, hallazgos). target: archivo de config o carpeta de proyecto."""
    now = now or datetime.now(timezone.utc)
    if target is not None and target.is_file():
        servers = raw_from_file("archivo", target)
    else:
        servers = raw_inventory(project=target or Path.cwd(), **inv)
    findings = [f for client, name, server, base in servers for f in check_server(client, name, server, base, now, soon)]
    return len(servers), findings


def cmd_tokens(args: list[str], now: datetime | None = None) -> int:
    """agentguard tokens [carpeta | archivo_de_config] [--dias N]. Código 1 si hay ALTO o MEDIO."""
    soon = SOON_DAYS
    rest = []
    i = 0
    while i < len(args):
        if args[i] in ("--dias", "--days") and i + 1 < len(args) and args[i + 1].isdigit():
            soon = int(args[i + 1])
            i += 2
        else:
            rest.append(args[i])
            i += 1
    target = Path(rest[0]) if rest else None
    n, findings = scan_tokens(target, now, soon)
    if not n:
        print(t("No se encontraron servidores MCP en las configuraciones conocidas."))
        return 0
    for f in findings:
        client, _, rest_where = f.where.partition(" · ")
        print(f"[{t(f.level)}] {t(f.kind)} — {t(client)} · {rest_where}: {t(f.detail, **dict(f.values))}")
    serious = sum(1 for f in findings if f.level in ("ALTO", "MEDIO"))
    if not findings:
        print(t("(sin credenciales vencidas, por vencer ni en texto plano)"))
    print(t("\n{servers} servidor(es), {findings} hallazgo(s), {serious} ALTO/MEDIO. No se usó la red.",
            servers=n, findings=len(findings), serious=serious))
    return 1 if serious else 0
