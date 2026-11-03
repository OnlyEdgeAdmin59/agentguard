"""Reporte de auditoría en Markdown: junta scan, cve y trifecta.

Uso: agentguard audit [--skills carpeta] [--config archivo] [--proyecto carpeta] [--tools carpeta]
                      [--sin-red] [--out reporte.md]
Sin --config revisa las configs MCP instaladas (como `cve` y `trifecta`). --sin-red no consulta OSV.dev.
Sale con código 1 si hay hallazgos Críticos o Altos.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .cve import check, inventory, servers_from_file
from .scanner import collect, escalate, scan_file
from .trifecta import CAPS, LABEL, analyze, groups, scopes_of

SEVERITIES = ("Crítico", "Alto", "Medio", "Bajo", "Info")
OSV_SEVERITY = {"CRITICAL": "Crítico", "HIGH": "Alto", "MODERATE": "Medio", "MEDIUM": "Medio", "LOW": "Bajo"}

# Cómo arreglar cada regla de scan (primera palabra clave que aparece en el nombre de la regla)
FIX_SCAN = [
    ("Menciona secretos", "Confirma que solo explica dónde poner la llave y no le pide al modelo leerla."),
    ("Secreto", "Revísalo ya: pide leer credenciales y sacarlas. Desinstálalo, cambia las llaves que menciona "
                "y repórtalo al autor o al registro."),
    ("Anula instrucciones", "Quita el texto que pide ignorar instrucciones previas; una descripción legítima "
                            "nunca lo necesita. Si viene de un tercero, no instales esa versión."),
    ("ocultar algo", "Elimina la orden de ocultarle cosas al usuario. Si viene de un tercero, trátalo como "
                     "malicioso: desinstálalo y repórtalo."),
    ("escondidas", "Elimina la orden de actuar sin avisar. Si viene de un tercero, trátalo como malicioso."),
    ("shadowing", "Una tool no debe cambiar cómo se usan otras. Quita esa parte o desinstala el servidor."),
    ("Imagen markdown", "Quita imágenes con URLs armadas con datos y desactiva las imágenes remotas en el cliente."),
    ("parámetro", "Revisa por qué un parámetro recibe datos del contexto; limita el esquema a lo que la tool "
                  "necesita."),
    ("URL externa", "Confirma que el dominio es del autor y que el envío hace falta; si no, quítalo."),
    ("urgencia", "Quita etiquetas tipo <IMPORTANT> dirigidas al modelo; una descripción honesta no las necesita."),
    ("comentario HTML", "Elimina comentarios HTML con instrucciones: el usuario no los ve, el modelo sí."),
    ("base64", "Decodifica el bloque y revísalo; si no es un dato necesario (imagen, certificado), quítalo."),
    ("invisibles", "Elimina los caracteres invisibles (U+200B, tags U+E00xx, bidi) con un editor que los muestre."),
]
FIX_DEFAULT = "Revisa el fragmento y decide si es legítimo."
MAX_PLACES = 5  # lugares que se listan por regla MEDIO agrupada


@dataclass
class Item:
    severidad: str
    origen: str  # scan, cve o trifecta
    titulo: str
    donde: str
    detalle: str
    arreglo: str


@dataclass
class Audit:
    items: list[Item] = field(default_factory=list)
    resumen: list[str] = field(default_factory=list)


def show(path: str | Path) -> str:
    """Ruta relativa a la carpeta actual si cae dentro; si no, tal cual."""
    try:
        return Path(path).resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


def fix_for(rule: str) -> str:
    return next((fix for key, fix in FIX_SCAN if key.lower() in rule.lower()), FIX_DEFAULT)


def audit_scan(skills: Path, out: Audit) -> None:
    files = collect(skills)
    with redirect_stdout(io.StringIO()):
        findings = [f for f in escalate([f for p in files for f in scan_file(p)]) if f.level != "PISTA"]
    where = lambda f: f"{show(f.source.split('::')[0])}:{f.line}"  # noqa: E731
    for f in findings:
        if f.level == "ALTO":
            out.items.append(Item("Alto", "scan", f.rule, where(f), f"«{f.snippet}»", fix_for(f.rule)))
    medios: dict[str, list] = {}
    for f in findings:  # los MEDIO se agrupan por regla para que el reporte se pueda leer
        if f.level == "MEDIO":
            medios.setdefault(f.rule, []).append(f)
    for rule, group in medios.items():
        files = {f.source.split("::")[0] for f in group}
        shown = ", ".join(where(f) for f in group[:MAX_PLACES]) + (" …" if len(group) > MAX_PLACES else "")
        detail = f"«{group[0].snippet}»" if len(group) == 1 else f"{len(group)} veces en {len(files)} archivo(s): {shown}"
        out.items.append(Item("Medio", "scan", rule, where(group[0]) if len(group) == 1 else "varios", detail,
                              fix_for(rule)))
    altos = sum(f.level == "ALTO" for f in findings)
    out.resumen.append(f"**scan**: {len(files)} archivo(s) revisados, {len(findings)} hallazgo(s), {altos} ALTO(s).")


def audit_cve(servers: list, check_fn, out: Audit) -> None:
    for s in servers:
        if s.note:
            what = f"{s.package.name} ({s.package.ecosystem})" if s.package else s.name
            fix = ("Fija la versión exacta (`pkg@1.2.3` / `pkg==1.2.3`) para que no cambie sin que lo apruebes."
                   if "no fijada" in s.note else "Revísalo a mano: no se puede consultar en OSV.")
            out.items.append(Item("Info", "cve", f"{what}: {s.note}", f"{s.client} · {s.name}", "", fix))
    packages = [s.package for s in servers if s.package and s.package.version]
    if check_fn is None:
        out.resumen.append(f"**cve**: {len(servers)} servidor(es); OSV.dev no se consultó (--sin-red).")
        return
    try:
        vulns = check_fn(packages)
    except OSError as e:
        out.items.append(Item("Info", "cve", "No se pudo consultar OSV.dev", "red", str(e),
                              "Vuelve a correr `agentguard cve` con conexión."))
        out.resumen.append(f"**cve**: {len(servers)} servidor(es); OSV.dev no respondió.")
        return
    for v in vulns:
        fixed = v.fixed != "sin corrección"
        fix = (f"Actualiza {v.package.name} a {v.fixed}." if fixed
               else "No hay versión corregida: quita el servidor o aíslalo.")
        detail = f"{v.id} · severidad {v.severity}" + (f" · {v.summary}" if v.summary else "")
        out.items.append(Item(OSV_SEVERITY.get(v.severity.upper(), "Medio"), "cve",
                              f"{v.cve} en {v.package.name} {v.package.version}", v.package.ecosystem, detail, fix))
    out.resumen.append(f"**cve**: {len(servers)} servidor(es), {len(packages)} con versión fija consultados en "
                       f"OSV.dev, {len(vulns)} vulnerabilidad(es).")


def audit_trifecta(scopes: dict, out: Audit) -> None:
    hits = 0
    for label, group in scopes.items():
        r = analyze(group)
        by_name = {s.name: s for s in group}
        if r.estado == "triada":
            hits += 1
            parts = []
            for c in CAPS:
                names = ", ".join(f"{n} ({by_name[n].caps[c].origen})" for n in r.aporta[c])
                parts.append(f"{LABEL[c]}: {names}")
            fix = "Quita una de estas opciones: " + " | ".join(", ".join(o) for o in r.quitar) + "."
            if r.solo:
                fix += f" {', '.join(r.solo)} junta las tres solo: limita sus tools (solo lectura, repos permitidos)."
            out.items.append(Item("Alto", "trifecta", "Tríada letal", label, "; ".join(parts), fix))
        elif r.estado == "posible":
            out.items.append(Item("Medio", "trifecta", "Posible tríada letal", label,
                                  f"Falta «{LABEL[r.faltan[0]].lower()}»; sin clasificar: {', '.join(r.sin_clasificar)}",
                                  "Revisa las tools de esos servidores (o pásalas con --tools) y vuelve a correr."))
    out.resumen.append(f"**trifecta**: tríada letal en {hits} de {len(scopes)} alcance(s) (global y cada proyecto).")


def build(skills: Path | None = None, config: Path | None = None, project: Path | None = None,
          tools_dir: Path | None = None, check_fn=check) -> Audit:
    out = Audit()
    if skills is not None:
        audit_scan(skills, out)
    project = project or Path.cwd()
    servers = servers_from_file("archivo", config) if config else inventory(project=project)
    audit_cve(servers, check_fn, out)
    if config:
        scopes = {f"archivo · {k}": v for k, v in scopes_of(config, tools_dir).items()}
    else:
        scopes = groups(project, tools_dir)
    audit_trifecta(scopes, out)
    return out


def overall(items: list[Item]) -> str:
    sev = {i.severidad for i in items}
    return "Alto" if sev & {"Crítico", "Alto"} else "Medio" if "Medio" in sev else "Bajo"


def render(audit: Audit, when: date | None = None, scope: str = "") -> str:
    when = when or date.today()
    counts = {s: sum(i.severidad == s for i in audit.items) for s in SEVERITIES}
    lines = ["# Auditoría de seguridad de agentes (AgentGuard)", "", f"Fecha: {when.isoformat()}"]
    if scope:
        lines += ["", f"Alcance: {scope}"]
    lines += ["", "## Resumen ejecutivo", "", f"**Riesgo general: {overall(audit.items)}.**", ""]
    lines += [f"- {r}" for r in audit.resumen]
    lines += ["", "| severidad | hallazgos |", "|---|---|"] + [f"| {s} | {n} |" for s, n in counts.items()]
    lines += ["", "## Hallazgos por severidad", ""]
    n = 0
    for sev in SEVERITIES:
        items = [i for i in audit.items if i.severidad == sev]
        if not items:
            continue
        lines += [f"### {sev} ({len(items)})", ""]
        for i in items:
            n += 1
            lines.append(f"**H-{n:02d} · {i.titulo}** — {i.origen} · {i.donde}")
            if i.detalle:
                lines.append(f"- Detalle: {i.detalle}")
            lines += [f"- Cómo arreglar: {i.arreglo}", ""]
    if not n:
        lines += ["Sin hallazgos.", ""]
    lines += [
        "## Revisión manual",
        "",
        "> Para completar por quien audita. Lo automático no reemplaza esta parte.",
        "",
        "- [ ] Hallazgos confirmados y descartados (por ID):",
        "- [ ] Permisos reales de cada servidor (tokens, carpetas, cuentas):",
        "- [ ] Origen y mantenedor de cada servidor (¿cambió de dueño o de repo?):",
        "- [ ] Tools revisadas a mano (salida de tools/list):",
        "- [ ] Skills de terceros leídas completas:",
        "- [ ] Conclusión:",
        "",
        "Auditor: ________ · Fecha: ________",
        "",
        "## Límites",
        "",
        "- `scan` usa reglas fijas: en un set de validación ciego detectó 10 de 23 ataques (43%) y tuvo 1 falso "
        "positivo de 23. Que no haya hallazgos no prueba que algo sea seguro.",
        "- `trifecta` clasifica con una tabla de servidores conocidos y, si no están, con heurística por palabras; "
        "lo heurístico hay que confirmarlo a mano.",
        "- `cve` solo encuentra vulnerabilidades publicadas en OSV.dev para paquetes con versión fija.",
        "- No se ejecutó ningún servidor.",
    ]
    return "\n".join(lines) + "\n"


def cmd_audit(args: list[str], check_fn=check) -> int:
    opts = {}
    flags = {"--skills", "--config", "--proyecto", "--tools", "--out"}
    i = 0
    while i < len(args):
        if args[i] in flags and i + 1 < len(args):
            opts[args[i]] = Path(args[i + 1])
            i += 2
        elif args[i] == "--sin-red":
            check_fn = None
            i += 1
        else:
            print(__doc__)
            return 2
    audit = build(opts.get("--skills"), opts.get("--config"), opts.get("--proyecto"), opts.get("--tools"), check_fn)
    scope = ", ".join(f"{k[2:]} `{show(v)}`" for k, v in opts.items() if k != "--out") or "configs MCP instaladas"
    text = render(audit, scope=scope)
    if "--out" in opts:
        opts["--out"].write_text(text, encoding="utf-8")
        print(f"Reporte guardado en {opts['--out']} ({len(audit.items)} hallazgo(s), riesgo {overall(audit.items)})")
    else:
        print(text)
    return 1 if any(i.severidad in ("Crítico", "Alto") for i in audit.items) else 0
