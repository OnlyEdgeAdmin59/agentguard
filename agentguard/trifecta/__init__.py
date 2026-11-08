"""Tríada letal (Simon Willison): datos privados + contenido no confiable + salida hacia afuera.

Si una misma configuración de agente junta las tres, un texto malicioso que llegue por el contenido
no confiable puede hacer que el agente lea datos privados y los mande afuera.
Cada servidor MCP se clasifica primero con la tabla curada (known.json) y, si no está, con
heurística sobre su nombre, comando, variables de entorno y (con --tools) sus tools.
Solo lee archivos locales; no ejecuta los servidores ni usa la red.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..i18n import t, t_scope
from ..cve.inventory import NPM, config_paths, first_positional, package_of, servers_in, strip_jsonc

KNOWN = Path(__file__).resolve().parent / "known.json"
PRIV, UNTRUSTED, OUT = "privado", "no_confiable", "salida"
CAPS = (PRIV, UNTRUSTED, OUT)
LABEL = {PRIV: "Lee datos privados", UNTRUSTED: "Trae contenido no confiable", OUT: "Envía hacia afuera"}

# Heurística: palabras sueltas (se separan por _ - . / : @ y espacios; se acepta plural con s)
WORDS = {
    PRIV: {"file", "filesystem", "fs", "directory", "folder", "git", "repo", "repository", "database", "db", "sql",
           "sqlite", "postgres", "postgresql", "mysql", "mongo", "mongodb", "redis", "supabase", "gmail", "mail",
           "email", "inbox", "outlook", "drive", "gdrive", "dropbox", "onedrive", "notion", "obsidian", "vault",
           "calendar", "contact", "private", "confluence", "sheet"},
    UNTRUSTED: {"fetch", "web", "browser", "browse", "puppeteer", "playwright", "scrape", "scraper", "crawl",
                "crawler", "firecrawl", "search", "brave", "tavily", "url", "http", "rss", "feed", "inbox", "mail",
                "email", "gmail", "issue", "ticket", "reddit", "twitter", "youtube", "slack", "discord"},
    OUT: {"send", "post", "webhook", "notify", "notifier", "notification", "smtp", "slack", "discord", "telegram",
          "whatsapp", "sms", "twilio", "tweet", "publish", "upload", "push", "comment"},
}
DOCKER_OPTS = {"-e", "--env", "--env-file", "-v", "--volume", "--mount", "--name", "--network", "-p", "--publish",
               "-w", "--workdir", "-u", "--user", "--entrypoint", "--platform", "-l", "--label"}


@dataclass(frozen=True)
class Evidence:
    origen: str  # "tabla" o "heurística"
    motivo: str


@dataclass
class Classified:
    client: str
    name: str
    caps: dict[str, Evidence]
    clasificado: bool  # False = ni tabla ni heurística dijeron nada


@dataclass
class Result:
    estado: str  # "triada", "posible" o "sin_triada"
    aporta: dict[str, list[str]]
    faltan: list[str]
    sin_clasificar: list[str]
    solo: list[str] = field(default_factory=list)  # servidores que juntan las tres por sí solos
    quitar: list[list[str]] = field(default_factory=list)  # opciones mínimas para romper la tríada


def load_known(path: Path = KNOWN) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def docker_image(server: dict) -> str | None:
    args = [str(a) for a in server.get("args") or []]
    if Path(str(server.get("command", ""))).stem.lower() != "docker" or "run" not in args:
        return None
    image, _ = first_positional(args[args.index("run") + 1:], DOCKER_OPTS)
    if not image:
        return None
    image = image.split("@", 1)[0]
    head, _, last = image.rpartition("/")
    return (f"{head}/" if head else "") + last.split(":", 1)[0]


def keys_of(server: dict) -> tuple[set[str], list[str]]:
    """Claves para buscar en la tabla ('npm:pkg', 'docker:imagen') y URLs del servidor."""
    keys = set()
    pkg, _ = package_of(server)
    if pkg:
        keys.add(f"{'npm' if pkg.ecosystem == NPM else 'pypi'}:{pkg.name.lower()}")
    image = docker_image(server)
    if image:
        keys.add(f"docker:{image.lower()}")
    urls = [str(server["url"])] if server.get("url") else []
    urls += [str(a) for a in server.get("args") or [] if str(a).startswith(("http://", "https://"))]
    return keys, urls


def from_table(server: dict, known: list[dict]) -> dict | None:
    keys, urls = keys_of(server)
    for entry in known:
        for match in entry["coincide"]:
            if match.lower() in keys:
                return entry
            if match.startswith("url:") and any(match[4:] in u.lower() for u in urls):
                return entry
    return None


def words_in(text: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9]+", text.lower()) if w]


def hits(text: str, cap: str) -> list[str]:
    found = []
    for w in words_in(text):
        if (w in WORDS[cap] or (w.endswith("s") and w[:-1] in WORDS[cap])) and w not in found:
            found.append(w)
    return found


def heuristic(name: str, server: dict, tools: list[dict]) -> dict[str, Evidence]:
    sources = [("nombre", name), ("comando", " ".join([str(server.get("command", ""))] +
                                                      [str(a) for a in server.get("args") or []]))]
    if server.get("url"):
        sources.append(("url", str(server["url"])))
    if isinstance(server.get("env"), dict):
        sources.append(("variables de entorno", " ".join(server["env"])))
    sources += [(f"tool {t.get('name', '?')}", f"{t.get('name', '')} {t.get('description', '')}")
                for t in tools if isinstance(t, dict)]
    out = {}
    for cap in CAPS:
        parts = [f"{', '.join(h)} ({where})" for where, text in sources if (h := hits(text, cap))]
        if parts:
            out[cap] = Evidence("heurística", "; ".join(parts))
    return out


def classify_full(name: str, server: dict, tools: list[dict] | None = None,
                  known: list[dict] | None = None) -> tuple[dict[str, Evidence], bool]:
    entry = from_table(server, load_known() if known is None else known)
    if entry is not None:
        return {c: Evidence("tabla", entry["motivo"]) for c in entry["capacidades"]}, True
    caps = heuristic(name, server, tools or [])
    return caps, bool(caps)


def classify(name: str, server: dict, tools: list[dict] | None = None) -> dict[str, Evidence]:
    return classify_full(name, server, tools)[0]


def tools_for(name: str, tools_dir: Path | None) -> list[dict]:
    """Tools de un servidor desde <tools_dir>/<nombre>.json (salida de tools/list)."""
    if tools_dir is None:
        return []
    try:
        data = json.loads((tools_dir / f"{name}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    tools = data.get("tools") if isinstance(data, dict) else data
    return tools if isinstance(tools, list) else []


def read_data(path: Path) -> object:
    try:
        return json.loads(strip_jsonc(path.read_text(encoding="utf-8", errors="replace")))
    except (OSError, json.JSONDecodeError):
        return None


def read_servers(path: Path) -> dict[str, dict]:
    """Todos los servidores del archivo mezclados (incluye los de todos los proyectos)."""
    return servers_in(read_data(path))


def split_scopes(data: object) -> tuple[dict[str, dict], dict[str, dict[str, dict]]]:
    """Servidores globales y los de cada proyecto (~/.claude.json: "projects": {ruta: {"mcpServers": ...}})."""
    if not isinstance(data, dict):
        return {}, {}
    top = servers_in({k: v for k, v in data.items() if k != "projects"})
    raw = data.get("projects") if isinstance(data.get("projects"), dict) else {}
    projects = {}
    for where, proj in raw.items():
        if isinstance(proj, dict):
            projects[where] = servers_in({"mcpServers": proj.get("mcpServers")})
    return top, projects


def same_path(a: str | Path, b: str | Path) -> bool:
    norm = lambda p: os.path.normcase(os.path.normpath(os.path.abspath(str(p))))  # noqa: E731
    return norm(a) == norm(b)


def classify_all(client: str, servers: dict[str, dict], tools_dir: Path | None) -> list[Classified]:
    known = load_known()
    out = []
    for name, server in servers.items():
        caps, ok = classify_full(name, server, tools_for(name, tools_dir), known)
        out.append(Classified(client, name, caps, ok))
    return out


def servers_of(path: Path, tools_dir: Path | None = None, client: str = "archivo") -> list[Classified]:
    return classify_all(client, read_servers(path), tools_dir)


def scoped(top: dict[str, dict], projects: dict[str, dict[str, dict]]) -> dict[str, dict[str, dict]]:
    """Cada proyecto hereda los globales; un proyecto sin servidores propios no se repite."""
    out = {"global": top} if top else {}
    out.update({f"proyecto {where}": {**top, **own} for where, own in projects.items() if own})
    return out


def scopes_of(path: Path, tools_dir: Path | None = None, client: str = "archivo") -> dict[str, list[Classified]]:
    """Servidores de un archivo de config agrupados por alcance real: global y cada proyecto."""
    return {label: classify_all(client, servers, tools_dir)
            for label, servers in scoped(*split_scopes(read_data(path))).items()}


def groups(project: Path, tools_dir: Path | None = None, system: str | None = None, home: Path | None = None,
           env=None) -> dict[str, list[Classified]]:
    """Por cliente y alcance: global, cada proyecto de ~/.claude.json y la carpeta revisada
    (sus .mcp.json / .cursor / .vscode). Cada proyecto hereda los servidores globales de su cliente."""
    system, home = system or sys.platform, home or Path.home()
    env = os.environ if env is None else env
    global_paths = config_paths(system, home, env, None)
    project_paths = [p for p in config_paths(system, home, env, project) if p not in global_paths]
    tops: dict[str, dict] = {}
    projects: dict[str, dict[str, dict]] = {}
    seen: set[Path] = set()
    for client, path in global_paths + project_paths:
        if not path.is_file() or path.resolve() in seen:
            continue
        seen.add(path.resolve())
        top, own = split_scopes(read_data(path))
        tops.setdefault(client, {})
        projects.setdefault(client, {})
        if (client, path) in project_paths:
            projects[client].setdefault(str(project), {}).update(top)
            continue
        tops[client].update(top)
        for where, servers in own.items():
            key = str(project) if same_path(where, project) else where
            projects[client].setdefault(key, {}).update(servers)
    out = {}
    for client in tops:
        target = projects[client].pop(str(project), None)  # la carpeta revisada va al final
        if target is not None:
            projects[client][str(project)] = target
        for label, servers in scoped(tops[client], projects[client]).items():
            out[f"{client} · {label}"] = classify_all(client, servers, tools_dir)
    return out


def analyze(group: list[Classified]) -> Result:
    aporta = {c: [s.name for s in group if c in s.caps] for c in CAPS}
    faltan = [c for c in CAPS if not aporta[c]]
    sin_clasificar = [s.name for s in group if not s.clasificado]
    if faltan:
        estado = "posible" if sin_clasificar and len(faltan) == 1 else "sin_triada"
        return Result(estado, aporta, faltan, sin_clasificar)
    solo = [s.name for s in group if all(c in s.caps for c in CAPS)]
    smallest = min(len(v) for v in aporta.values())
    quitar: list[list[str]] = []
    for c in CAPS:
        if len(aporta[c]) == smallest and aporta[c] not in quitar:
            quitar.append(aporta[c])
    return Result("triada", aporta, [], sin_clasificar, solo, quitar)


def describe(server: Classified, cap: str) -> str:
    ev = server.caps[cap]
    check = t(" — confirmar a mano") if ev.origen == "heurística" else ""
    return f"{server.name} ({t(ev.origen)}: {t_motivo(ev.motivo)}{check})"


def t_motivo(motivo: str) -> str:
    """Traduce el motivo de la tabla o el de la heurística ('fetch (nombre); web (url)')."""
    if t(motivo) != motivo:
        return t(motivo)
    return re.sub(r"\((nombre|comando|url|variables de entorno)\)", lambda m: f"({t(m.group(1))})", motivo)


def report(client: str, group: list[Classified]) -> Result:
    result = analyze(group)
    by_name = {s.name: s for s in group}
    print(t("\n== {client}: {n} servidor(es)", client=t_scope(client), n=len(group)))
    if result.estado == "triada":
        print(t("[ALTO] TRÍADA LETAL: esta configuración junta las tres capacidades."))
        for c in CAPS:
            print(f"  - {t(LABEL[c])}: " + "; ".join(describe(by_name[n], c) for n in result.aporta[c]))
        for name in result.solo:
            print(t("  ! {name} junta las tres por sí solo: quítalo o limita sus tools "
                    "(solo lectura, repos o canales permitidos).", name=name))
        print(t("Para romperla, quita una de estas opciones (lo que menos servidores toca):"))
        for option in result.quitar:
            broken = [t(LABEL[c]).lower() for c in CAPS if set(result.aporta[c]) <= set(option)]
            print(t("  • {option}  → ya nadie {broken}", option=", ".join(option), broken=" / ".join(broken)))
    elif result.estado == "posible":
        missing = t(LABEL[result.faltan[0]]).lower()
        print(t("[MEDIO] POSIBLE TRÍADA: ya hay dos capacidades y falta «{missing}».", missing=missing))
        print(t("  Sin clasificar (podrían aportarla): {names}. Revísalos o pasa sus tools con --tools <carpeta>.",
                names=", ".join(result.sin_clasificar)))
    else:
        print(t("Sin tríada: falta {missing}.", missing=", ".join(t(LABEL[c]).lower() for c in result.faltan)))
        if result.sin_clasificar:
            print(t("  [INFO] Sin clasificar: {names}", names=", ".join(result.sin_clasificar)))
    for s in group:
        found = ", ".join(f"{t(c)} ({t(s.caps[c].origen)})" for c in CAPS if c in s.caps)
        print(f"  {s.name:<24} {found or t('ninguna' if s.clasificado else 'sin clasificar')}")
    return result


def cmd_trifecta(args: list[str]) -> int:
    """agentguard trifecta [carpeta_del_proyecto | archivo_de_config] [--tools carpeta]. Código 1 si hay tríada."""
    tools_dir = None
    if "--tools" in args:
        i = args.index("--tools")
        tools_dir = Path(args[i + 1]) if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
    target = Path(args[0]) if args else Path.cwd()
    if target.is_file():
        found = {f"archivo · {label}": g for label, g in scopes_of(target, tools_dir).items()}
    else:
        found = groups(target, tools_dir)
    if not any(found.values()):
        print(t("No se encontraron servidores MCP en las configuraciones conocidas."))
        return 0
    results = [report(client, group) for client, group in found.items() if group]
    return 1 if any(r.estado == "triada" for r in results) else 0
