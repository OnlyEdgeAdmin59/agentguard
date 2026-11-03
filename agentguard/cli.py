"""agentguard: seguridad para skills (SKILL.md) y herramientas MCP (JSON).

Uso:
  agentguard scan   <carpeta> [--all]   detecta tool poisoning
                                      (--all incluye node_modules, CHANGELOG, etc.)
  agentguard lock   <carpeta>   guarda huellas en agentguard.lock.json
  agentguard verify <carpeta>   alerta si algo cambió (rug pull)
  agentguard cve [carpeta]      CVE conocidos de los servidores MCP instalados (OSV.dev)
  agentguard trifecta [carpeta] [--tools dir]
                                tríada letal: datos privados + contenido no confiable + salida
Sale con código 1 si hay hallazgos ALTOS o cambios (útil para CI).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .scanner import collect, escalate, fingerprints, lock_path, scan_file

IN_GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"


def annotate(level: str, file: str, line: int, msg: str) -> None:
    """En GitHub Actions marca el hallazgo en la línea del PR."""
    if not IN_GITHUB:
        return
    kind = "error" if level == "ALTO" else "warning"
    loc = f"file={file.split('::')[0]},line={max(line, 1)}"
    print(f"::{kind} {loc},title=agentguard {level}::{msg}")


def cmd_scan(target: Path, include_all: bool = False) -> int:
    files = collect(target, include_all)
    findings = [f for f in escalate([f for p in files for f in scan_file(p)]) if f.level != "PISTA"]
    for f in findings:
        print(f"[{f.level}] {f.rule} — {f.source}:{f.line}  «{f.snippet}»")
        annotate(f.level, f.source, f.line, f"{f.rule}: {f.snippet}")
    altos = sum(f.level == "ALTO" for f in findings)
    hint = "" if include_all else " (excluye node_modules, CHANGELOG, LICENSE…; usá --all para incluirlos)"
    print(f"\n{len(files)} archivo(s), {len(findings)} hallazgo(s), {altos} ALTO(s){hint}")
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
        print("No hay lock. Corré primero: agentguard lock <carpeta>")
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
    # Windows redirige a archivo en cp1252: forzar UTF-8 y no romper por caracteres raros
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    if argv[1:] == ["--version"]:
        from . import __version__
        print(f"agentguard {__version__}")
        return 0
    if len(argv) >= 2 and argv[1] == "cve":
        from .cve import cmd_cve  # import tardío: scan/lock/verify no lo necesitan
        return cmd_cve(argv[2:])
    if len(argv) >= 2 and argv[1] == "trifecta":
        from .trifecta import cmd_trifecta
        return cmd_trifecta(argv[2:])
    include_all = "--all" in argv
    argv = [a for a in argv if a != "--all"]
    if len(argv) == 2 and argv[1] not in COMMANDS:  # compatibilidad: scan por defecto
        argv = [argv[0], "scan", argv[1]]
    if len(argv) != 3 or argv[1] not in COMMANDS:
        print(__doc__)
        return 2
    if argv[1] == "scan":
        return cmd_scan(Path(argv[2]), include_all)
    return COMMANDS[argv[1]](Path(argv[2]))


def run() -> None:
    """Punto de entrada del comando `agentguard` instalado con pip."""
    sys.exit(main(sys.argv))
