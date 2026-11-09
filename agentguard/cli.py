"""agentguard: seguridad para skills (SKILL.md) y herramientas MCP (JSON).

Uso:
  agentguard scan   <carpeta> [--all]   detecta tool poisoning
                                      (--all incluye node_modules, CHANGELOG, etc.)
                    [--deep]          además, juicio semántico con un modelo de IA (opcional;
                                      envía el texto a Anthropic salvo con --deep-provider ollama)
                    [--deep-provider anthropic|ollama] [--deep-model nombre] [--deep-yes]
                    [--deep-dry-run] [--deep-fail-on high]
  agentguard lock  <carpeta>   guarda huellas en agentguard.lock.json
  agentguard verify <carpeta>   alerta si algo cambió (rug pull)
  agentguard cve [carpeta]      CVE conocidos de los servidores MCP instalados (OSV.dev)
  agentguard trifecta [carpeta] [--tools dir]
                                tríada letal: datos privados + contenido no confiable + salida
  agentguard audit [--skills dir] [--config archivo] [--sin-red] [--out reporte.md]
                                reporte de auditoría en Markdown (scan + cve + trifecta)
Opción global: --lang en (o AGENTGUARD_LANG=en) para salida en inglés.
Sale con código 1 si hay hallazgos ALTOS o cambios (útil para CI); los de --deep solo con --deep-fail-on high.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .i18n import get_lang, pop_lang, t
from .scanner import collect, escalate, fingerprints, lock_path, scan_file

USAGE_EN = """agentguard: security for AI agent skills (SKILL.md) and MCP tools (JSON).

Usage:
  agentguard scan   <folder> [--all]    detect tool poisoning
                                        (--all includes node_modules, CHANGELOG, etc.)
                    [--deep]            also a semantic check with an AI model (optional;
                                        sends the text to Anthropic unless --deep-provider ollama)
                    [--deep-provider anthropic|ollama] [--deep-model name] [--deep-yes]
                    [--deep-dry-run] [--deep-fail-on high]
  agentguard lock  <folder>   save fingerprints to agentguard.lock.json
  agentguard verify <folder>   alert if anything changed (rug pull)
  agentguard cve [folder]      known CVEs in installed MCP servers (OSV.dev)
  agentguard trifecta [folder] [--tools dir]
                               lethal trifecta: private data + untrusted content + outbound
  agentguard audit [--skills dir] [--config file] [--project dir] [--tools dir] [--offline] [--out report.md]
                               Markdown audit report (scan + cve + trifecta)
Global option: --lang en (or AGENTGUARD_LANG=en) for English output.
Exits with code 1 on HIGH findings or changes (useful in CI); --deep findings only with --deep-fail-on high.
"""

IN_GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"


def annotate(level: str, file: str, line: int, msg: str) -> None:
    """En GitHub Actions marca el hallazgo en la línea del PR."""
    if not IN_GITHUB:
        return
    kind = "error" if level == "ALTO" else "warning"
    loc = f"file={file.split('::')[0]},line={max(line, 1)}"
    print(f"::{kind} {loc},title=agentguard {t(level)}::{msg}")


def print_finding(f) -> None:
    print(f"[{t(f.level)}] {t(f.rule)} — {f.source}:{f.line}  «{f.snippet}»")
    if f.reason:
        print("       " + t("motivo: {reason}", reason=f.reason))
    annotate(f.level, f.source, f.line, f"{t(f.rule)}: {f.reason or f.snippet}")


def cmd_scan(target: Path, include_all: bool = False, deep_opts=None) -> int:
    files = collect(target, include_all)
    findings = [f for f in escalate([f for p in files for f in scan_file(p)]) if f.level != "PISTA"]
    for f in findings:
        print_finding(f)
    altos = sum(f.level == "ALTO" for f in findings)
    hint = "" if include_all else t(" (excluye node_modules, CHANGELOG, LICENSE…; usá --all para incluirlos)")
    print(t("\n{files} archivo(s), {findings} hallazgo(s), {high} ALTO(s){hint}",
            files=len(files), findings=len(findings), high=altos, hint=hint))
    code = 1 if altos else 0
    if deep_opts is not None and deep_opts.enabled:
        from . import deep_cli  # import tardío: sin --deep no se carga
        print()
        result = deep_cli.session(files, deep_opts)
        if isinstance(result, int):
            return code or result  # si --deep no corrió, no tapa el ALTO de las reglas
        deep_findings, stats = result
        for f in deep_findings:
            print_finding(f)
        print(deep_cli.summary(deep_findings, stats))
        if deep_opts.fail_on_high and any(f.level == "ALTO" for f in deep_findings):
            code = 1
    return code


def cmd_lock(target: Path) -> int:
    prints = fingerprints(target)
    lock_path(target).write_text(json.dumps(prints, indent=2, sort_keys=True), encoding="utf-8")
    print(t("Guardadas {n} huella(s) en {path}", n=len(prints), path=lock_path(target)))
    return 0


def cmd_verify(target: Path) -> int:
    try:
        old = json.loads(lock_path(target).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(t("No hay lock. Corré primero: agentguard lock <carpeta>"))
        return 2
    new = fingerprints(target)
    changed = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    for k in changed:
        print(t("[ALTO] CAMBIÓ desde que lo aprobaste: {k}", k=k))
        annotate("ALTO", str(lock_path(target).parent / k), 1, t("Cambió desde que se aprobó (posible rug pull)"))
    for k in added:
        print(t("[MEDIO] Nuevo, sin aprobar: {k}", k=k))
    for k in removed:
        print(t("[INFO] Eliminado: {k}", k=k))
    if not (changed or added or removed):
        print(t("Todo igual que cuando lo aprobaste."))
    return 1 if changed or added else 0


COMMANDS = {"scan": cmd_scan, "lock": cmd_lock, "verify": cmd_verify}


def main(argv: list[str]) -> int:
    # Windows redirige a archivo en cp1252: forzar UTF-8 y no romper por caracteres raros
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    argv = pop_lang(list(argv))
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
    if len(argv) >= 2 and argv[1] == "audit":
        from .audit import cmd_audit
        return cmd_audit(argv[2:])
    include_all = "--all" in argv
    argv = [a for a in argv if a != "--all"]
    deep_opts = None
    if any(a.startswith("--deep") for a in argv):
        from .deep_cli import pop_deep
        parsed = pop_deep(argv)
        if isinstance(parsed, str):
            print(parsed)
            return 2
        deep_opts, argv = parsed
    if len(argv) == 2 and argv[1] not in COMMANDS:  # compatibilidad: scan por defecto
        argv = [argv[0], "scan", argv[1]]
    if len(argv) != 3 or argv[1] not in COMMANDS:
        print(USAGE_EN if get_lang() == "en" else __doc__)
        return 2
    if argv[1] == "scan":
        return cmd_scan(Path(argv[2]), include_all, deep_opts)
    if deep_opts is not None:
        print(t("--deep solo funciona con scan y audit"))
        return 2
    return COMMANDS[argv[1]](Path(argv[2]))


def run() -> None:
    """Punto de entrada del comando `agentguard` instalado con pip."""
    sys.exit(main(sys.argv))
