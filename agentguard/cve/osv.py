"""Consulta vulnerabilidades conocidas en OSV.dev (API pública, sin cuenta).

Privacidad: a OSV solo se envía nombre del paquete, ecosistema y versión (querybatch)
y luego el ID de cada vulnerabilidad para leer su detalle. Nunca descripciones de tools,
rutas, nombres de servidores ni nada más de la configuración.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable

from .inventory import Package

OSV_API = "https://api.osv.dev/v1"
TIMEOUT = 20

PostFn = Callable[[str, dict], dict]
GetFn = Callable[[str], dict]


@dataclass(frozen=True)
class Vuln:
    package: Package
    id: str
    cve: str        # primer alias CVE-…, o el ID de OSV si no tiene CVE
    severity: str   # CRITICAL / HIGH / MODERATE / LOW, o vector CVSS, o "desconocida"
    fixed: str      # versión(es) corregida(s), o "sin corrección"
    summary: str = ""


def http_post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "agentguard"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 (URL fija https)
        return json.loads(resp.read().decode("utf-8"))


def http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "agentguard"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def query_of(pkg: Package) -> dict:
    """Lo único que sale de la máquina por paquete."""
    return {"package": {"name": pkg.name, "ecosystem": pkg.ecosystem}, "version": pkg.version}


def batch_ids(packages: list[Package], post: PostFn = http_post) -> dict[Package, list[str]]:
    """IDs de vulnerabilidades por paquete (sigue next_page_token si OSV pagina)."""
    ids: dict[Package, list[str]] = {p: [] for p in packages}
    pending = [(p, None) for p in packages]
    while pending:
        queries = []
        for pkg, token in pending:
            q = query_of(pkg)
            if token:
                q["page_token"] = token
            queries.append(q)
        results = post(f"{OSV_API}/querybatch", {"queries": queries}).get("results", [])
        nxt = []
        for (pkg, _), res in zip(pending, results):
            ids[pkg] += [v["id"] for v in res.get("vulns", []) if isinstance(v, dict) and "id" in v]
            if res.get("next_page_token"):
                nxt.append((pkg, res["next_page_token"]))
        pending = nxt
    return ids


def severity_of(vuln: dict, pkg: Package) -> str:
    label = (vuln.get("database_specific") or {}).get("severity")
    if isinstance(label, str) and label:
        return label.upper()
    for aff in vuln.get("affected", []):
        label = (aff.get("ecosystem_specific") or {}).get("severity")
        if isinstance(label, str) and label:
            return label.upper()
    for sev in vuln.get("severity", []):
        if sev.get("score"):
            return str(sev["score"])
    return "desconocida"


def same_package(aff: dict, pkg: Package) -> bool:
    p = aff.get("package") or {}
    name = p.get("name", "")
    if pkg.ecosystem == "PyPI":
        name = name.replace("_", "-").replace(".", "-").lower()
    return p.get("ecosystem") == pkg.ecosystem and name == pkg.name


def fixed_of(vuln: dict, pkg: Package) -> str:
    fixed = []
    for aff in vuln.get("affected", []):
        if not same_package(aff, pkg):
            continue
        for rng in aff.get("ranges", []):
            for ev in rng.get("events", []):
                if ev.get("fixed") and ev["fixed"] not in fixed:
                    fixed.append(ev["fixed"])
    return ", ".join(fixed) or "sin corrección"


def to_vuln(pkg: Package, vuln_id: str, detail: dict) -> Vuln:
    cves = [a for a in detail.get("aliases", []) if isinstance(a, str) and a.startswith("CVE-")]
    if vuln_id.startswith("CVE-"):
        cves.insert(0, vuln_id)
    return Vuln(pkg, vuln_id, cves[0] if cves else vuln_id, severity_of(detail, pkg),
                fixed_of(detail, pkg), str(detail.get("summary", ""))[:120])


def check(packages: Iterable[Package], post: PostFn = http_post, get: GetFn = http_get) -> list[Vuln]:
    """Vulnerabilidades conocidas para paquetes con versión fija. Los demás se ignoran."""
    pinned = sorted({p for p in packages if p.version}, key=lambda p: (p.ecosystem, p.name, p.version))
    if not pinned:
        return []
    out: list[Vuln] = []
    cache: dict[str, dict] = {}
    for pkg, ids in batch_ids(pinned, post).items():
        for vid in dict.fromkeys(ids):
            if vid not in cache:
                cache[vid] = get(f"{OSV_API}/vulns/{vid}")
            out.append(to_vuln(pkg, vid, cache[vid]))
    return out
