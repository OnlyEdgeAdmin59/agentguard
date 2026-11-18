"""Módulo CVE: inventario de servidores MCP y consulta de vulnerabilidades en OSV.dev."""
from __future__ import annotations

from pathlib import Path

from ..i18n import t, t_note
from .inventory import Package, Server, inventory, servers_from_file
from .osv import Vuln, check
from .status import GRAVES, Status, check_status

__all__ = ["Package", "Server", "Status", "Vuln", "check", "check_status", "inventory", "servers_from_file",
           "cmd_cve", "print_status"]

NO_STATUS = ("--sin-estado", "--no-status")


def print_status(statuses: list[Status]) -> None:
    for st in statuses:
        level = "ALTO" if st.kind in GRAVES else "INFO"
        version = f" {st.package.version}" if st.package.version else ""
        print(f"[{t(level)}] {st.package.name}{version} ({st.package.ecosystem}): {t(st.kind)} — {t(st.template, **dict(st.values))}")


def cmd_cve(args: list[str], check_fn=check, status_fn=check_status) -> int:
    """agentguard cve [carpeta_del_proyecto | archivo_de_config] [--sin-estado].

    Código 1 si hay vulnerabilidades o paquetes obsoletos / retirados / inexistentes.
    """
    if any(a in NO_STATUS for a in args):
        status_fn = None
    args = [a for a in args if a not in NO_STATUS]
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
    serious = 0
    if status_fn is not None:
        try:
            statuses = status_fn([s.package for s in servers if s.package])
        except OSError as e:  # sin red: avisa pero no tumba el comando por esto
            statuses = []
            print(t("[INFO] No se pudo consultar el estado en npm/PyPI: {e}", e=e))
        if statuses:
            print(t("\nEstado en el registro (npm / PyPI):"))
            print_status(statuses)
        serious = sum(1 for st in statuses if st.kind in GRAVES)
    print(t("\n{servers} servidor(es), {packages} con versión fija consultados, {vulns} vulnerabilidad(es)",
            servers=len(servers), packages=len(packages), vulns=len(vulns)))
    if status_fn is not None:
        print(t("{n} paquete(s) obsoleto(s), retirado(s) o inexistente(s)", n=serious))
    return 1 if vulns or serious else 0
