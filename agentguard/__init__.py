"""agentguard: seguridad para skills (SKILL.md) y herramientas MCP (JSON).

Paquete: `scanner` (reglas y escaneo), `cli` (comandos), `cve` (inventario MCP + OSV.dev),
`trifecta` (tríada letal), `audit` (reporte de auditoría).
"""
__version__ = "0.5.0"

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
    "__version__", "RULES", "Finding", "cmd_lock", "cmd_scan", "cmd_verify", "collect", "escalate", "fingerprints",
    "main", "normalize", "run", "scan_file", "scan_text",
]
