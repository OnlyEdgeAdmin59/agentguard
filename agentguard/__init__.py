"""agentguard: seguridad para skills (SKILL.md) y herramientas MCP (JSON).

Paquete: `scanner` (reglas y escaneo), `cli` (comandos scan/lock/verify/cve), `cve` (inventario MCP + OSV.dev).
"""
from .cli import cmd_lock, cmd_scan, cmd_verify, main, run
from .scanner import (
    RULES,
    Finding,
    collect,
    escalate,
    fingerprints,
    normalize,
    scan_file,
    scan_text,
)

__all__ = [
    "RULES", "Finding", "cmd_lock", "cmd_scan", "cmd_verify", "collect", "escalate", "fingerprints",
    "main", "normalize", "run", "scan_file", "scan_text",
]
