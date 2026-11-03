"""Inventario de servidores MCP instalados: qué paquete, de qué ecosistema y qué versión.

Lee las configuraciones de Claude Desktop, Claude Code, Cursor y VS Code (Windows, macOS, Linux)
y saca el paquete de comandos como `npx -y pkg@1.2.3` o `uvx pkg==1.2.3`. Solo lee archivos locales.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Mapping

NPM, PYPI = "npm", "PyPI"


@dataclass(frozen=True)
class Package:
    name: str
    ecosystem: str
    version: str | None  # None = no fijada (npx/uvx bajan la última)


@dataclass(frozen=True)
class Server:
    client: str
    config: str
    name: str
    package: Package | None
    note: str = ""  # por qué no hay paquete o versión


def config_paths(system: str, home: Path, env: Mapping[str, str], project: Path | None = None) -> list[tuple[str, Path]]:
    """Dónde guarda cada cliente su configuración MCP. system: 'win32', 'darwin' o 'linux'."""
    if system == "win32":
        appdata = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
        desktop = appdata / "Claude"
        code_user = appdata / "Code" / "User"
    elif system == "darwin":
        support = home / "Library" / "Application Support"
        desktop = support / "Claude"
        code_user = support / "Code" / "User"
    else:
        config = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
        desktop = config / "Claude"
        code_user = config / "Code" / "User"
    paths = [
        ("Claude Desktop", desktop / "claude_desktop_config.json"),
        ("Claude Code", home / ".claude.json"),
        ("Cursor", home / ".cursor" / "mcp.json"),
        ("VS Code", code_user / "mcp.json"),
        ("VS Code", code_user / "settings.json"),
    ]
    if project is not None:
        paths += [
            ("Claude Code", project / ".mcp.json"),
            ("Cursor", project / ".cursor" / "mcp.json"),
            ("VS Code", project / ".vscode" / "mcp.json"),
        ]
    return paths


def strip_jsonc(text: str) -> str:
    """Quita comentarios // y /* */ y comas finales (VS Code usa JSON con comentarios)."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            i = text.find("\n", i)
            i = n if i == -1 else i
        elif text.startswith("/*", i):
            i = text.find("*/", i + 2)
            i = n if i == -1 else i + 2
        else:
            out.append(c)
            i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def servers_in(data: object) -> dict[str, dict]:
    """Junta los servidores de todas las formas conocidas de config."""
    found: dict[str, dict] = {}
    if not isinstance(data, dict):
        return found
    for key in ("mcpServers", "servers"):  # Claude/Cursor | VS Code mcp.json
        if isinstance(data.get(key), dict):
            found.update({k: v for k, v in data[key].items() if isinstance(v, dict)})
    mcp = data.get("mcp")  # VS Code settings.json: "mcp": {"servers": ...}
    if isinstance(mcp, dict) and isinstance(mcp.get("servers"), dict):
        found.update({k: v for k, v in mcp["servers"].items() if isinstance(v, dict)})
    projects = data.get("projects")  # ~/.claude.json: servidores por proyecto
    if isinstance(projects, dict):
        for proj in projects.values():
            if isinstance(proj, dict) and isinstance(proj.get("mcpServers"), dict):
                found.update({k: v for k, v in proj["mcpServers"].items() if isinstance(v, dict)})
    return found


EXACT_VERSION = re.compile(r"^v?\d+(\.\d+){0,3}([-+.][0-9A-Za-z.-]+)?$")
PYPI_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?")


def parse_npm_spec(spec: str) -> Package:
    """'@scope/pkg@1.2.3' → (@scope/pkg, 1.2.3). Rangos o tags (latest, ^1) = versión no fijada."""
    at = spec.rfind("@")
    name, version = (spec[:at], spec[at + 1:]) if at > 0 else (spec, None)
    return Package(name, NPM, version.lstrip("v") if version and EXACT_VERSION.match(version) else None)


def parse_pypi_spec(spec: str) -> Package:
    """'pkg==1.2.3', 'pkg@1.2.3', 'pkg[extra]==1.2.3' → paquete PyPI."""
    m = PYPI_NAME.match(spec)
    name = m.group(1) if m else spec
    rest = spec[m.end():] if m else ""
    version = None
    pinned = re.match(r"^\s*(==|@)\s*([^\s,;]+)\s*$", rest)
    if pinned and EXACT_VERSION.match(pinned.group(2)):
        version = pinned.group(2).lstrip("v")
    return Package(re.sub(r"[-_.]+", "-", name).lower(), PYPI, version)


def first_positional(args: list[str], takes_value: set[str]) -> tuple[str | None, dict[str, str]]:
    """Primer argumento que no es una opción, y las opciones con valor que se vieron."""
    opts: dict[str, str] = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return (args[i + 1] if i + 1 < len(args) else None), opts
        if a.startswith("-"):
            key, eq, val = a.partition("=")
            if key in takes_value:
                if eq:
                    opts[key] = val
                elif i + 1 < len(args):
                    opts[key] = args[i + 1]
                    i += 1
            i += 1
            continue
        return a, opts
    return None, opts


def command_name(command: str) -> str:
    name = PurePath(command.replace("\\", "/")).name.lower()
    return re.sub(r"\.(cmd|exe|bat|ps1)$", "", name)


def package_of(server: dict) -> tuple[Package | None, str]:
    """Paquete que ejecuta un servidor MCP local, o None con el motivo."""
    if server.get("url") and not server.get("command"):
        return None, "servidor remoto (URL), sin paquete local"
    command = server.get("command")
    args = [str(a) for a in server.get("args") or [] if isinstance(a, (str, int, float))]
    if not isinstance(command, str) or not command:
        return None, "sin comando"
    cmd = command_name(command)
    if cmd == "cmd" and args and args[0].lower() == "/c":  # Windows: cmd /c npx ...
        return package_of({"command": args[1], "args": args[2:]}) if len(args) > 1 else (None, "sin comando")
    if cmd in ("pnpm", "yarn") and args[:1] == ["dlx"]:
        cmd, args = "npx", args[1:]
    if cmd == "npm" and args[:1] == ["exec"]:
        cmd, args = "npx", args[1:]
    if cmd == "uv" and args[:2] == ["tool", "run"]:
        cmd, args = "uvx", args[2:]
    if cmd == "pipx" and args[:1] == ["run"]:
        spec, opts = first_positional(args[1:], {"--spec", "--python"})
        spec = opts.get("--spec", spec)
        return (parse_pypi_spec(spec), "") if spec else (None, "pipx sin paquete")
    if cmd in ("npx", "bunx"):
        spec, opts = first_positional(args, {"-p", "--package", "-c", "--call"})
        spec = opts.get("--package") or opts.get("-p") or spec
        return (parse_npm_spec(spec), "") if spec else (None, "npx sin paquete")
    if cmd == "uvx":
        spec, opts = first_positional(args, {"--from", "--with", "--python", "-p", "--index", "--index-url"})
        spec = opts.get("--from", spec)
        return (parse_pypi_spec(spec), "") if spec else (None, "uvx sin paquete")
    return None, f"comando '{cmd}' no indica un paquete npm/PyPI"


def servers_from_file(client: str, path: Path) -> list[Server]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        data = json.loads(strip_jsonc(text))
    except json.JSONDecodeError:
        return [Server(client, str(path), "?", None, "JSON inválido")]
    out = []
    for name, server in servers_in(data).items():
        pkg, note = package_of(server)
        if pkg and pkg.version is None and not note:
            note = "versión no fijada (se ejecuta la última)"
        out.append(Server(client, str(path), name, pkg, note))
    return out


def inventory(project: Path | None = None, system: str | None = None, home: Path | None = None,
              env: Mapping[str, str] | None = None) -> list[Server]:
    """Todos los servidores MCP de las configs que existen en esta máquina."""
    paths = config_paths(system or sys.platform, home or Path.home(), os.environ if env is None else env, project)
    seen: set[Path] = set()
    out: list[Server] = []
    for client, path in paths:
        if path.is_file() and path.resolve() not in seen:
            seen.add(path.resolve())
            out.extend(servers_from_file(client, path))
    return out
