"""Módulo CVE: inventario de servidores MCP y consulta de vulnerabilidades en OSV.dev."""
from __future__ import annotations

from pathlib import Path

from ..i18n import t, t_note
from .inventory import Package, Server, inventory, servers_from_file
from .osv import Vuln, check

__all__ = ["Package", "Server", "Vuln", "check", "inventory", "servers_from_file", "cmd_cve"]


def cmd_cve(args: list[str], check_fn=check) -> int:
    """agentguard cve [carpeta_del_proyecto | archivo_de_config]. Código 1 si hay vulnerabilidades."""
    target = Path(args[0]) if args else Path.cwd()
    if target.is_file():
        servers = servers_from_file("archivo", target)
    else:
        servers = inventory(project=target)
    if not servers:
        print(t("No se encontraron servidores MCP en las configuraciones conocidas."))
        return 0
    packages = [s.package for s in servers if s.package and s.package.version]
    try:
        vulns = check_fn(packages)
    except OSError as e:  # sin red, timeout, error HTTP
        print(t("No se pudo consultar OSV.dev: {e}", e=e))
        return 2
    print(f"{t('paquete'):<40} {t('versión'):<12} {'CVE':<22} {t('severidad'):<10} {t('corregida')}")
    for v in vulns:
        print(f"{v.package.name:<40} {v.package.version:<12} {v.cve:<22} {t(v.severity)[:10]:<10} {t(v.fixed)}")
    if not vulns:
        print(t("(sin vulnerabilidades conocidas en los paquetes con versión fija)"))
    for s in servers:
        if s.note:
            what = f"{s.package.name} ({s.package.ecosystem})" if s.package else "—"
            print(f"[INFO] {t(s.client)} · {s.name}: {what} — {t_note(s.note)}")
    print(t("\n{servers} servidor(es), {packages} con versión fija consultados, {vulns} vulnerabilidad(es)",
            servers=len(servers), packages=len(packages), vulns=len(vulns)))
    return 1 if vulns else 0
