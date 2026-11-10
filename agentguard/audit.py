"""Reporte de auditoría en Markdown: junta scan, cve y trifecta.

Uso: agentguard audit [--skills carpeta] [--config archivo] [--proyecto carpeta] [--tools carpeta]
                      [--sin-red] [--out reporte.md]
Sin --config revisa las configs MCP instaladas (como `cve` y `trifecta`). --sin-red no consulta OSV.dev.
En inglés: --project equivale a --proyecto y --offline a --sin-red.
--deep (con --skills) suma el juicio semántico de un modelo; mismas opciones --deep-* que scan.
Sale con código 1 si hay hallazgos Críticos o Altos (los de --deep solo con --deep-fail-on high).
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .i18n import get_lang, t, t_note, t_scope
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
USAGE_EN = """Markdown audit report: combines scan, cve and trifecta.

Usage: agentguard audit [--skills folder] [--config file] [--project folder] [--tools folder]
                        [--offline] [--out report.md]
Without --config it checks the installed MCP configs (like `cve` and `trifecta`). --offline skips OSV.dev.
--deep (with --skills) adds a semantic judgment from a model; same --deep-* options as scan.
Exits with code 1 on Critical or High findings (--deep ones only with --deep-fail-on high).
"""
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
    limites: list[str] = field(default_factory=list)  # límites extra según lo que se corrió (p. ej. --deep)


DEEP_SEVERITY = {"ALTO": "Alto", "MEDIO": "Medio", "INFO": "Info"}
DEEP_FIX = ("Lee la skill o tool completa y confirma si esa instrucción hace falta; si no, quítala o no la "
            "instales.")


def audit_deep(findings: list, stats, provider: str, out: Audit) -> None:
    from .deep_cli import summary
    for f in findings:
        detail = (f"«{f.snippet}» — {t(f.reason)}" if f.snippet else t(f.reason)).strip(" —")
        out.items.append(Item(DEEP_SEVERITY.get(f.level, "Info"), "deep", t(f.rule),
                              f"{show(f.source.split('::')[0])}:{f.line}", detail, t(DEEP_FIX)))
    out.resumen.append(summary(findings, stats))
    sent = (t("el texto se envió a {host}", host="api.anthropic.com") if provider == "anthropic"
            else t("corrió local con Ollama"))
    out.limites.append(t("- `--deep` usó {model} ({sent}). El juicio de un modelo no es determinista y puede "
                         "equivocarse en ambos sentidos; confírmalo a mano.", model=stats.model, sent=sent))


def show(path: str | Path) -> str:
    """Ruta relativa a la carpeta actual si cae dentro; si no, tal cual."""
    try:
        return Path(path).resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


def fix_for(rule: str) -> str:
    return t(next((fix for key, fix in FIX_SCAN if key.lower() in rule.lower()), FIX_DEFAULT))


def audit_scan(skills: Path, out: Audit) -> None:
    files = collect(skills)
    with redirect_stdout(io.StringIO()):
        findings = [f for f in escalate([f for p in files for f in scan_file(p)]) if f.level != "PISTA"]
    where = lambda f: f"{show(f.source.split('::')[0])}:{f.line}"  # noqa: E731
    for f in findings:
        if f.level == "ALTO":
            out.items.append(Item("Alto", "scan", t(f.rule), where(f), f"«{f.snippet}»", fix_for(f.rule)))
    medios: dict[str, list] = {}
    for f in findings:  # los MEDIO se agrupan por regla para que el reporte se pueda leer
        if f.level == "MEDIO":
            medios.setdefault(f.rule, []).append(f)
    for rule, group in medios.items():
        files = {f.source.split("::")[0] for f in group}
        shown = ", ".join(where(f) for f in group[:MAX_PLACES]) + (" …" if len(group) > MAX_PLACES else "")
        detail = (f"«{group[0].snippet}»" if len(group) == 1
                  else t("{n} veces en {files} archivo(s): {shown}", n=len(group), files=len(files), shown=shown))
        out.items.append(Item("Medio", "scan", t(rule), where(group[0]) if len(group) == 1 else t("varios"), detail,
                              fix_for(rule)))
    altos = sum(f.level == "ALTO" for f in findings)
    out.resumen.append(t("**scan**: {files} archivo(s) revisados, {findings} hallazgo(s), {high} ALTO(s).",
                         files=len(files), findings=len(findings), high=altos))


def audit_cve(servers: list, check_fn, out: Audit) -> None:
    for s in servers:
        if s.note:
            what = f"{s.package.name} ({s.package.ecosystem})" if s.package else s.name
            fix = t("Fija la versión exacta (`pkg@1.2.3` / `pkg==1.2.3`) para que no cambie sin que lo apruebes."
                    if "no fijada" in s.note else "Revísalo a mano: no se puede consultar en OSV.")
            out.items.append(Item("Info", "cve", f"{what}: {t_note(s.note)}", f"{t(s.client)} · {s.name}", "", fix))
    packages = [s.package for s in servers if s.package and s.package.version]
    if check_fn is None:
        out.resumen.append(t("**cve**: {servers} servidor(es); OSV.dev no se consultó (--sin-red).", servers=len(servers)))
        return
    try:
        vulns = check_fn(packages)
    except OSError as e:
        out.items.append(Item("Info", "cve", t("No se pudo consultar OSV.dev"), t("red"), str(e),
                              t("Vuelve a correr `agentguard cve` con conexión.")))
        out.resumen.append(t("**cve**: {servers} servidor(es); OSV.dev no respondió.", servers=len(servers)))
        return
    for v in vulns:
        fixed = v.fixed != "sin corrección"
        fix = (t("Actualiza {pkg} a {fixed}.", pkg=v.package.name, fixed=v.fixed) if fixed
               else t("No hay versión corregida: quita el servidor o aíslalo."))
        detail = t("{id} · severidad {severity}", id=v.id, severity=t(v.severity)) + (f" · {v.summary}" if v.summary else "")
        out.items.append(Item(OSV_SEVERITY.get(v.severity.upper(), "Medio"), "cve",
                              t("{cve} en {pkg} {version}", cve=v.cve, pkg=v.package.name, version=v.package.version),
                              v.package.ecosystem, detail, fix))
    out.resumen.append(t("**cve**: {servers} servidor(es), {packages} con versión fija consultados en OSV.dev, "
                         "{vulns} vulnerabilidad(es).", servers=len(servers), packages=len(packages), vulns=len(vulns)))


def audit_trifecta(scopes: dict, out: Audit) -> None:
    hits = 0
    for label, group in scopes.items():
        r = analyze(group)
        by_name = {s.name: s for s in group}
        if r.estado == "triada":
            hits += 1
            parts = []
            for c in CAPS:
                names = ", ".join(f"{n} ({t(by_name[n].caps[c].origen)})" for n in r.aporta[c])
                parts.append(f"{t(LABEL[c])}: {names}")
            fix = t("Quita una de estas opciones: {options}.", options=" | ".join(", ".join(o) for o in r.quitar))
            if r.solo:
                fix += t(" {names} junta las tres solo: limita sus tools (solo lectura, repos permitidos).",
                         names=", ".join(r.solo))
            out.items.append(Item("Alto", "trifecta", t("Tríada letal"), t_scope(label), "; ".join(parts), fix))
        elif r.estado == "posible":
            out.items.append(Item("Medio", "trifecta", t("Posible tríada letal"), t_scope(label),
                                  t("Falta «{missing}»; sin clasificar: {names}", missing=t(LABEL[r.faltan[0]]).lower(),
                                    names=", ".join(r.sin_clasificar)),
                                  t("Revisa las tools de esos servidores (o pásalas con --tools) y vuelve a correr.")))
    out.resumen.append(t("**trifecta**: tríada letal en {hits} de {scopes} alcance(s) (global y cada proyecto).",
                         hits=hits, scopes=len(scopes)))


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
    lines = [t("# Auditoría de seguridad de agentes (AgentGuard)"), "", t("Fecha: {date}", date=when.isoformat())]
    if scope:
        lines += ["", t("Alcance: {scope}", scope=scope)]
    lines += ["", t("## Resumen ejecutivo"), "", t("**Riesgo general: {risk}.**", risk=t(overall(audit.items))), ""]
    lines += [f"- {r}" for r in audit.resumen]
    lines += ["", t("| severidad | hallazgos |"), "|---|---|"] + [f"| {t(s)} | {n} |" for s, n in counts.items()]
    lines += ["", t("## Hallazgos por severidad"), ""]
    n = 0
    for sev in SEVERITIES:
        items = [i for i in audit.items if i.severidad == sev]
        if not items:
            continue
        lines += [f"### {t(sev)} ({len(items)})", ""]
        for i in items:
            n += 1
            lines.append(f"**H-{n:02d} · {i.titulo}** — {i.origen} · {i.donde}")
            if i.detalle:
                lines.append(t("- Detalle: {detail}", detail=i.detalle))
            lines += [t("- Cómo arreglar: {fix}", fix=i.arreglo), ""]
    if not n:
        lines += [t("Sin hallazgos."), ""]
    lines += [t(x) for x in [
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
        "- En un set ciego independiente (Skill-Inject, MIT: 34 ataques en 60 textos), las reglas solas marcaron "
        "como ALTO 2 de 34 ataques (6%); con `--deep` (Claude Haiku), 31 de 34 (91%). En 120 benignos, `--deep` "
        "dio 2 falsas alarmas ALTAS y 11 tuvieron algún aviso (9%). En 1170 SKILL.md reales, `--deep` marcó 30 "
        "como ALTO (2,6%, todos falsas alarmas al revisarlos a mano) y el 39% tuvo algún aviso. Es una sola "
        "medición; el modelo puede variar entre corridas. `--deep` envía el texto a Anthropic y necesita "
        "ANTHROPIC_API_KEY. Que no haya hallazgos no prueba que algo sea seguro.",
        "- `cve`, `trifecta` y `lock`/`verify` no dependen de las reglas de `scan` ni de `--deep`.",
        "- `trifecta` clasifica con una tabla de servidores conocidos y, si no están, con heurística por palabras; "
        "lo heurístico hay que confirmarlo a mano.",
        "- `cve` solo encuentra vulnerabilidades publicadas en OSV.dev para paquetes con versión fija.",
        "- No se ejecutó ningún servidor.",
    ]] + audit.limites
    return "\n".join(lines) + "\n"


def cmd_audit(args: list[str], check_fn=check, deep_transport=None) -> int:
    deep_opts = None
    if any(a.startswith("--deep") for a in args):
        from .deep_cli import pop_deep
        parsed = pop_deep(args)
        if isinstance(parsed, str):
            print(parsed)
            return 2
        deep_opts, args = parsed
    opts = {}
    flags = {"--skills", "--config", "--proyecto", "--tools", "--out"}
    args = ["--proyecto" if a == "--project" else "--sin-red" if a == "--offline" else a for a in args]
    i = 0
    while i < len(args):
        if args[i] in flags and i + 1 < len(args):
            opts[args[i]] = Path(args[i + 1])
            i += 2
        elif args[i] == "--sin-red":
            check_fn = None
            i += 1
        else:
            print(USAGE_EN if get_lang() == "en" else __doc__)
            return 2
    if deep_opts is not None and deep_opts.enabled and "--skills" not in opts:
        print(t("--deep en audit necesita --skills <carpeta>"))
        return 2
    audit = build(opts.get("--skills"), opts.get("--config"), opts.get("--proyecto"), opts.get("--tools"), check_fn)
    if deep_opts is not None and deep_opts.enabled:
        from .deep_cli import session
        result = session(collect(opts["--skills"]), deep_opts, transport=deep_transport)
        if isinstance(result, int):
            return result
        audit_deep(*result, deep_opts.provider, audit)
    names ={"--proyecto": "project"} if get_lang() == "en" else {}
    scope = (", ".join(f"{names.get(k, k[2:])} `{show(v)}`" for k, v in opts.items() if k != "--out")
             or t("configs MCP instaladas"))
    text = render(audit, scope=scope)
    if "--out" in opts:
        opts["--out"].write_text(text, encoding="utf-8")
        print(t("Reporte guardado en {path} ({n} hallazgo(s), riesgo {risk})",
                path=opts["--out"], n=len(audit.items), risk=t(overall(audit.items))))
    else:
        print(text)
    fail_deep = deep_opts is not None and deep_opts.fail_on_high
    return 1 if any(i.severidad in ("Crítico", "Alto") and (i.origen != "deep" or fail_deep)
                    for i in audit.items) else 0
