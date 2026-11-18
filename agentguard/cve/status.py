"""Estado de los paquetes MCP en su registro: obsoleto, retirado, abandonado o inexistente.

Cubre lo que OSV no ve (caso MCPhantom, nov-2026): agentes de IA que instalan paquetes MCP
deprecados o que ya no existen porque su conocimiento quedó congelado en el entrenamiento.
Un paquete puede estar archivado "sin garantías de seguridad" y no tener ningún CVE.

Privacidad: a registry.npmjs.org / pypi.org solo se pide el nombre del paquete (lo mismo
que pide npx o uvx al instalarlo). Nunca rutas, args ni nada más de la configuración.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional

from .inventory import NPM, PYPI, Package

NPM_REGISTRY = "https://registry.npmjs.org"
PYPI_API = "https://pypi.org/pypi"
TIMEOUT = 20
ABANDONED_MONTHS = 24

# Tipos de estado. Los "graves" hacen fallar el comando (código 1); "abandonado" solo avisa.
OBSOLETO, RETIRADA, INEXISTENTE, ABANDONADO = "obsoleto", "versión retirada", "no existe", "abandonado"
GRAVES = {OBSOLETO, RETIRADA, INEXISTENTE}

# Plantillas que se muestran (claves de i18n.EN)
NO_EN_REGISTRO = "no está en {registry} (posible nombre inventado o tomado por un atacante)"
VERSION_NO_EXISTE = "la versión {version} no existe en {registry}"
MSG = "{msg}"
MSG_ACTUALIZAR = "{msg} — actualizar a {latest}"
SIN_VERSIONES = "sin versiones nuevas hace {months} meses"
RETIRADA_MOTIVO = "{version} fue retirada (yanked): {msg}"
RETIRADA_SIN = "{version} fue retirada (yanked)"
INACTIVO = "el autor lo marcó como inactivo (Development Status :: 7 - Inactive)"

# GetFn devuelve el JSON, o None si el registro responde 404.
GetFn = Callable[[str], Optional[dict]]


@dataclass(frozen=True)
class Status:
    package: Package
    kind: str
    template: str = ""          # plantilla en español (se traduce al mostrar)
    values: tuple = ()          # (clave, valor) para la plantilla; mensajes del registro van tal cual

    @property
    def detail(self) -> str:
        return self.template.format(**dict(self.values))


def http_get(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "agentguard", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 (URL fija https)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def parse_time(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def months_since(dt: datetime, now: datetime) -> int:
    return (now.year - dt.year) * 12 + (now.month - dt.month)


def npm_url(name: str) -> str:
    return f"{NPM_REGISTRY}/{urllib.parse.quote(name, safe='@')}"


def npm_status(pkg: Package, doc: dict | None, now: datetime) -> list[Status]:
    if doc is None:
        return [Status(pkg, INEXISTENTE, NO_EN_REGISTRO, (("registry", "registry.npmjs.org"),))]
    versions = doc.get("versions") or {}
    latest = (doc.get("dist-tags") or {}).get("latest")
    out: list[Status] = []
    if pkg.version and pkg.version not in versions:
        out.append(Status(pkg, INEXISTENTE, VERSION_NO_EXISTE, (("version", pkg.version), ("registry", "npm"))))
    target = pkg.version if pkg.version in versions else latest
    msg = (versions.get(target) or {}).get("deprecated")
    if isinstance(msg, str) and msg:
        latest_msg = (versions.get(latest) or {}).get("deprecated")
        if pkg.version and target != latest and not latest_msg:
            out.append(Status(pkg, OBSOLETO, MSG_ACTUALIZAR, (("msg", msg.strip()[:160]), ("latest", latest))))
        else:
            out.append(Status(pkg, OBSOLETO, MSG, (("msg", msg.strip()[:160]),)))
        return out  # obsoleto ya dice más que abandonado
    times = [parse_time(v) for k, v in (doc.get("time") or {}).items() if k in versions]
    times = [x for x in times if x]
    if times and months_since(max(times), now) >= ABANDONED_MONTHS:
        out.append(Status(pkg, ABANDONADO, SIN_VERSIONES, (("months", months_since(max(times), now)),)))
    return out


def pypi_status(pkg: Package, doc: dict | None, now: datetime) -> list[Status]:
    if doc is None:
        return [Status(pkg, INEXISTENTE, NO_EN_REGISTRO, (("registry", "pypi.org"),))]
    releases = doc.get("releases") or {}
    info = doc.get("info") or {}
    out: list[Status] = []
    if pkg.version:
        files = releases.get(pkg.version)
        if files is None:
            out.append(Status(pkg, INEXISTENTE, VERSION_NO_EXISTE, (("version", pkg.version), ("registry", "PyPI"))))
        elif files and all(f.get("yanked") for f in files):
            reason = next((f.get("yanked_reason") for f in files if f.get("yanked_reason")), "")
            if reason:
                out.append(Status(pkg, RETIRADA, RETIRADA_MOTIVO, (("version", pkg.version), ("msg", reason))))
            else:
                out.append(Status(pkg, RETIRADA, RETIRADA_SIN, (("version", pkg.version),)))
    if any("Development Status :: 7 - Inactive" in c for c in info.get("classifiers") or []):
        out.append(Status(pkg, OBSOLETO, INACTIVO))
        return out
    times = [parse_time(f.get("upload_time_iso_8601") or f.get("upload_time", ""))
             for files in releases.values() for f in files or []]
    times = [x for x in times if x]
    if times and months_since(max(times), now) >= ABANDONED_MONTHS:
        out.append(Status(pkg, ABANDONADO, SIN_VERSIONES, (("months", months_since(max(times), now)),)))
    return out


def check_status(packages: Iterable[Package], get: GetFn = http_get,
                 now: datetime | None = None) -> list[Status]:
    """Estado en el registro de cada paquete (con o sin versión fija). Uno por nombre de paquete."""
    now = now or datetime.now(timezone.utc)
    out: list[Status] = []
    cache: dict[str, dict | None] = {}
    for pkg in sorted(set(packages), key=lambda p: (p.ecosystem, p.name, p.version or "")):
        if pkg.ecosystem == NPM:
            url, fn = npm_url(pkg.name), npm_status
        elif pkg.ecosystem == PYPI:
            url, fn = f"{PYPI_API}/{urllib.parse.quote(pkg.name)}/json", pypi_status
        else:
            continue
        if url not in cache:
            cache[url] = get(url)
        out += fn(pkg, cache[url], now)
    return out
