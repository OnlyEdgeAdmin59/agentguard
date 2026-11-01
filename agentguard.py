"""agentguard: seguridad para skills (SKILL.md) y herramientas MCP (JSON).

Uso:
  python agentguard.py scan   <carpeta>   detecta tool poisoning
  python agentguard.py lock   <carpeta>   guarda huellas en agentguard.lock.json
  python agentguard.py verify <carpeta>   alerta si algo cambió (rug pull)
Sale con código 1 si hay hallazgos ALTOS o cambios (útil para CI).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# (nivel, nombre, patrón). Reglas simples v1; luego se suma un modelo que confirme.
RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ("ALTO", "Anula instrucciones previas",
     re.compile(r"ignore (all |any )?(previous|prior|above) (instructions|rules)", re.I)),
    ("ALTO", "Pide ocultar algo al usuario",
     re.compile(r"(do not|don't|never) (tell|inform|mention|reveal|show)[^.]{0,40}(user|human)", re.I)),
    ("MEDIO", "Menciona secretos",
     re.compile(r"(\.ssh|id_rsa|\.env\b|\.aws/credentials|api[_-]?key|private key|mcp\.json)", re.I)),
    ("ALTO", "Envío de datos a URL externa",
     re.compile(r"(send|post|upload|forward|exfiltrate)[^.]{0,60}https?://", re.I)),
    ("MEDIO", "Etiquetas de urgencia para el modelo",
     re.compile(r"<\s*(important|system|secret|instructions?)\s*>", re.I)),
    ("MEDIO", "Comentario HTML oculto",
     re.compile(r"<!--.*?-->", re.S)),
    ("MEDIO", "Bloque base64 largo",
     re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")),
    ("ALTO", "Caracteres invisibles (texto escondido)",
     re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\U000e0000-\U000e007f]")),
]


@dataclass
class Finding:
    level: str
    rule: str
    source: str
    line: int
    snippet: str


def scan_text(text: str, source: str) -> list[Finding]:
    findings = []
    for level, name, pattern in RULES:
        for m in pattern.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            snippet = m.group(0).replace("\n", " ")[:80]
            findings.append(Finding(level, name, source, line, snippet))
    return findings


COMBO_SECRET = "Menciona secretos"
COMBO_SEND = "Envío de datos a URL externa"


def escalate(findings: list[Finding]) -> list[Finding]:
    """Un secreto solo es MEDIO; secreto + envío externo en la misma fuente es ALTO."""
    by_source: dict[str, set[str]] = {}
    for f in findings:
        by_source.setdefault(f.source, set()).add(f.rule)
    extra = []
    for source, rules in by_source.items():
        if COMBO_SECRET in rules and COMBO_SEND in rules:
            first = next(f for f in findings if f.source == source and f.rule == COMBO_SECRET)
            extra.append(Finding("ALTO", "Secreto + envío externo (posible robo)", source, first.line, first.snippet))
    return findings + extra


def texts_from_mcp_json(data: object, path: str = "") -> list[tuple[str, str]]:
    """Extrae description/inputSchema de una lista de herramientas MCP."""
    out: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            sub = f"{path}.{key}" if path else key
            if key in ("description", "title") and isinstance(value, str):
                out.append((sub, value))
            else:
                out.extend(texts_from_mcp_json(value, sub))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            out.extend(texts_from_mcp_json(item, f"{path}[{i}]"))
    return out


def scan_file(path: Path) -> list[Finding]:
    if path.stat().st_size > MAX_BYTES:
        return [Finding("MEDIO", "Archivo demasiado grande, no revisado", str(path), 0, "")]
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            pieces = texts_from_mcp_json(json.loads(text))
        except json.JSONDecodeError:
            return [Finding("MEDIO", "JSON inválido", str(path), 0, "")]
        return [f for src, t in pieces for f in scan_text(t, f"{path}::{src}")]
    return scan_text(text, str(path))


LOCK_NAME = "agentguard.lock.json"
MAX_BYTES = 2_000_000  # archivos más grandes se reportan, no se leen
IN_GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"


def annotate(level: str, file: str, line: int, msg: str) -> None:
    """En GitHub Actions marca el hallazgo en la línea del PR."""
    if not IN_GITHUB:
        return
    kind = "error" if level == "ALTO" else "warning"
    loc = f"file={file.split('::')[0]},line={max(line, 1)}"
    print(f"::{kind} {loc},title=agentguard {level}::{msg}")


def collect(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(
        p for p in target.rglob("*")
        if p.suffix.lower() in (".md", ".json") and p.name != LOCK_NAME
        and not p.is_symlink() and p.is_file()
    )


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprints(target: Path) -> dict[str, str]:
    """Una huella por archivo y, en MCP, una por herramienta (name+description+schema)."""
    base = target if target.is_dir() else target.parent
    prints: dict[str, str] = {}
    for path in collect(target):
        rel = path.relative_to(base).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        prints[rel] = sha(text)
        if path.suffix.lower() == ".json":
            try:
                tools = json.loads(text).get("tools", [])
            except (json.JSONDecodeError, AttributeError):
                continue
            for tool in tools if isinstance(tools, list) else []:
                if isinstance(tool, dict) and "name" in tool:
                    key = {k: tool.get(k) for k in ("name", "description", "inputSchema")}
                    prints[f"{rel}::tool:{tool['name']}"] = sha(json.dumps(key, sort_keys=True))
    return prints


def lock_path(target: Path) -> Path:
    return (target if target.is_dir() else target.parent) / LOCK_NAME


def cmd_scan(target: Path) -> int:
    files = collect(target)
    findings = escalate([f for p in files for f in scan_file(p)])
    for f in findings:
        print(f"[{f.level}] {f.rule} — {f.source}:{f.line}  «{f.snippet}»")
        annotate(f.level, f.source, f.line, f"{f.rule}: {f.snippet}")
    altos = sum(f.level == "ALTO" for f in findings)
    print(f"\n{len(files)} archivo(s), {len(findings)} hallazgo(s), {altos} ALTO(s)")
    return 1 if altos else 0


def cmd_lock(target: Path) -> int:
    prints = fingerprints(target)
    lock_path(target).write_text(json.dumps(prints, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Guardadas {len(prints)} huella(s) en {lock_path(target)}")
    return 0


def cmd_verify(target: Path) -> int:
    try:
        old = json.loads(lock_path(target).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("No hay lock. Corré primero: python agentguard.py lock <carpeta>")
        return 2
    new = fingerprints(target)
    changed = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    for k in changed:
        print(f"[ALTO] CAMBIÓ desde que lo aprobaste: {k}")
        annotate("ALTO", str(lock_path(target).parent / k), 1, "Cambió desde que se aprobó (posible rug pull)")
    for k in added:
        print(f"[MEDIO] Nuevo, sin aprobar: {k}")
    for k in removed:
        print(f"[INFO] Eliminado: {k}")
    if not (changed or added or removed):
        print("Todo igual que cuando lo aprobaste.")
    return 1 if changed or added else 0


COMMANDS = {"scan": cmd_scan, "lock": cmd_lock, "verify": cmd_verify}


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] not in COMMANDS:  # compatibilidad: scan por defecto
        argv = [argv[0], "scan", argv[1]]
    if len(argv) != 3 or argv[1] not in COMMANDS:
        print(__doc__)
        return 2
    return COMMANDS[argv[1]](Path(argv[2]))


def run() -> None:
    """Punto de entrada del comando `agentguard` instalado con pip."""
    sys.exit(main(sys.argv))


if __name__ == "__main__":
    run()
