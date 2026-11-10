"""Idioma de la salida (es / en). Solo traduce lo que se muestra; la lógica interna sigue en español.

Se elige con `--lang en` en cualquier comando o con la variable de entorno AGENTGUARD_LANG=en.
Por defecto: español.
"""
from __future__ import annotations

import os

LANGS = ("es", "en")
_lang = os.environ.get("AGENTGUARD_LANG", "es").strip().lower()[:2]
if _lang not in LANGS:
    _lang = "es"


def set_lang(lang: str) -> None:
    global _lang
    lang = (lang or "es").strip().lower()[:2]
    _lang = lang if lang in LANGS else "es"


def get_lang() -> str:
    return _lang


def pop_lang(argv: list[str]) -> list[str]:
    """Quita --lang X / --lang=X de los argumentos y fija el idioma."""
    out, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--lang" and i + 1 < len(argv):
            set_lang(argv[i + 1])
            i += 2
            continue
        if a.startswith("--lang="):
            set_lang(a.split("=", 1)[1])
            i += 1
            continue
        out.append(a)
        i += 1
    return out


def t(text: str, **kw) -> str:
    """Traduce una plantilla (o un valor suelto) y la formatea con kw."""
    if _lang == "en":
        text = EN.get(text, text)
    return text.format(**kw) if kw else text


# Plantillas y valores fijos que se muestran. Clave = texto en español tal cual está en el código.
EN: dict[str, str] = {
    # niveles
    "ALTO": "HIGH", "MEDIO": "MEDIUM", "INFO": "INFO", "PISTA": "HINT",
    # reglas de scan
    "Anula instrucciones previas": "Overrides previous instructions",
    "Pide ocultar algo al usuario": "Asks to hide something from the user",
    "Menciona secretos": "Mentions secrets",
    "Envío de datos a URL externa": "Sends data to an external URL",
    "Instrucción oculta en comentario HTML": "Hidden instruction in an HTML comment",
    "Bloque base64 largo": "Long base64 block",
    "Caracteres invisibles (texto escondido)": "Invisible characters (hidden text)",
    "Cambia cómo se usan otras herramientas (tool shadowing)": "Changes how other tools are used (tool shadowing)",
    "Pide hacer algo a escondidas": "Asks to do something covertly",
    "Mete datos en un parámetro de la tool": "Stuffs data into a tool parameter",
    "Instrucción escondida en base64": "Instruction hidden in base64",
    "Imagen markdown que filtra datos por la URL": "Markdown image leaking data through its URL",
    "Etiquetas de urgencia para el modelo": "Urgency tags aimed at the model",
    "Letras de otro alfabeto que imitan latinas (homoglifos)": "Letters from another alphabet imitating Latin (homoglyphs)",
    "Secreto + envío externo (posible robo)": "Secret + external send (possible theft)",
    "Secreto metido en un parámetro (posible robo)": "Secret stuffed into a parameter (possible theft)",
    "Archivo demasiado grande, no revisado": "File too large, not scanned",
    "JSON inválido": "Invalid JSON",
    # cli: scan / lock / verify
    "{file}:{line}": "{file}:{line}",
    " (excluye node_modules, CHANGELOG, LICENSE…; usá --all para incluirlos)":
        " (skips node_modules, CHANGELOG, LICENSE…; use --all to include them)",
    "\n{files} archivo(s), {findings} hallazgo(s), {high} ALTO(s){hint}":
        "\n{files} file(s), {findings} finding(s), {high} HIGH{hint}",
    "Guardadas {n} huella(s) en {path}": "Saved {n} fingerprint(s) to {path}",
    "No hay lock. Corré primero: agentguard lock <carpeta>": "No lock file. Run first: agentguard lock <folder>",
    "[ALTO] CAMBIÓ desde que lo aprobaste: {k}": "[HIGH] CHANGED since you approved it: {k}",
    "Cambió desde que se aprobó (posible rug pull)": "Changed since it was approved (possible rug pull)",
    "[MEDIO] Nuevo, sin aprobar: {k}": "[MEDIUM] New, not approved: {k}",
    "[INFO] Eliminado: {k}": "[INFO] Removed: {k}",
    "Todo igual que cuando lo aprobaste.": "Everything matches what you approved.",
    # cve
    "No se encontraron servidores MCP en las configuraciones conocidas.":
        "No MCP servers found in the known configurations.",
    "No se pudo consultar OSV.dev: {e}": "Could not query OSV.dev: {e}",
    "paquete": "package", "versión": "version", "severidad": "severity", "corregida": "fixed",
    "(sin vulnerabilidades conocidas en los paquetes con versión fija)":
        "(no known vulnerabilities in packages with a pinned version)",
    "\n{servers} servidor(es), {packages} con versión fija consultados, {vulns} vulnerabilidad(es)":
        "\n{servers} server(s), {packages} with a pinned version checked, {vulns} vulnerability(ies)",
    "servidor remoto (URL), sin paquete local": "remote server (URL), no local package",
    "sin comando": "no command",
    "comando '{cmd}' no indica un paquete npm/PyPI": "command '{cmd}' does not point to an npm/PyPI package",
    "versión no fijada (se ejecuta la última)": "version not pinned (runs the latest)",
    "sin corrección": "no fix", "desconocida": "unknown",
    # trifecta
    "Lee datos privados": "Reads private data",
    "Trae contenido no confiable": "Brings in untrusted content",
    "Envía hacia afuera": "Sends data out",
    "privado": "private", "no_confiable": "untrusted", "salida": "outbound",
    "tabla": "table", "heurística": "heuristic",
    "nombre": "name", "comando": "command", "url": "url", "variables de entorno": "environment variables",
    " — confirmar a mano": " — confirm manually",
    "\n== {client}: {n} servidor(es)": "\n== {client}: {n} server(s)",
    "[ALTO] TRÍADA LETAL: esta configuración junta las tres capacidades.":
        "[HIGH] LETHAL TRIFECTA: this configuration combines all three capabilities.",
    "  ! {name} junta las tres por sí solo: quítalo o limita sus tools (solo lectura, repos o canales permitidos).":
        "  ! {name} combines all three on its own: remove it or restrict its tools "
        "(read-only, allowed repos or channels).",
    "Para romperla, quita una de estas opciones (lo que menos servidores toca):":
        "To break it, remove one of these options (the one touching the fewest servers):",
    "  • {option}  → ya nadie {broken}": "  • {option}  → nothing left that {broken}",
    "[MEDIO] POSIBLE TRÍADA: ya hay dos capacidades y falta «{missing}».":
        "[MEDIUM] POSSIBLE TRIFECTA: two capabilities present, missing “{missing}”.",
    "  Sin clasificar (podrían aportarla): {names}. Revísalos o pasa sus tools con --tools <carpeta>.":
        "  Unclassified (could provide it): {names}. Review them or pass their tools with --tools <folder>.",
    "Sin tríada: falta {missing}.": "No trifecta: missing {missing}.",
    "  [INFO] Sin clasificar: {names}": "  [INFO] Unclassified: {names}",
    "ninguna": "none", "sin clasificar": "unclassified",
    "archivo": "file", "global": "global", "proyecto {where}": "project {where}",
    # audit
    "Crítico": "Critical", "Alto": "High", "Medio": "Medium", "Bajo": "Low", "Info": "Info",
    "varios": "multiple", "red": "network",
    "{n} veces en {files} archivo(s): {shown}": "{n} times in {files} file(s): {shown}",
    "**scan**: {files} archivo(s) revisados, {findings} hallazgo(s), {high} ALTO(s).":
        "**scan**: {files} file(s) scanned, {findings} finding(s), {high} HIGH.",
    "Fija la versión exacta (`pkg@1.2.3` / `pkg==1.2.3`) para que no cambie sin que lo apruebes.":
        "Pin the exact version (`pkg@1.2.3` / `pkg==1.2.3`) so it can't change without your approval.",
    "Revísalo a mano: no se puede consultar en OSV.": "Review it manually: it can't be checked against OSV.",
    "**cve**: {servers} servidor(es); OSV.dev no se consultó (--sin-red).":
        "**cve**: {servers} server(s); OSV.dev was not queried (--offline).",
    "No se pudo consultar OSV.dev": "Could not query OSV.dev",
    "Vuelve a correr `agentguard cve` con conexión.": "Run `agentguard cve` again with a network connection.",
    "**cve**: {servers} servidor(es); OSV.dev no respondió.": "**cve**: {servers} server(s); OSV.dev did not respond.",
    "Actualiza {pkg} a {fixed}.": "Upgrade {pkg} to {fixed}.",
    "No hay versión corregida: quita el servidor o aíslalo.": "No fixed version: remove the server or isolate it.",
    "{id} · severidad {severity}": "{id} · severity {severity}",
    "{cve} en {pkg} {version}": "{cve} in {pkg} {version}",
    "**cve**: {servers} servidor(es), {packages} con versión fija consultados en OSV.dev, {vulns} vulnerabilidad(es).":
        "**cve**: {servers} server(s), {packages} with a pinned version checked on OSV.dev, {vulns} vulnerability(ies).",
    "Quita una de estas opciones: {options}.": "Remove one of these options: {options}.",
    " {names} junta las tres solo: limita sus tools (solo lectura, repos permitidos).":
        " {names} combines all three on its own: restrict its tools (read-only, allowed repos).",
    "Tríada letal": "Lethal trifecta", "Posible tríada letal": "Possible lethal trifecta",
    "Falta «{missing}»; sin clasificar: {names}": "Missing “{missing}”; unclassified: {names}",
    "Revisa las tools de esos servidores (o pásalas con --tools) y vuelve a correr.":
        "Review those servers' tools (or pass them with --tools) and run again.",
    "**trifecta**: tríada letal en {hits} de {scopes} alcance(s) (global y cada proyecto).":
        "**trifecta**: lethal trifecta in {hits} of {scopes} scope(s) (global and each project).",
    "# Auditoría de seguridad de agentes (AgentGuard)": "# AI Agent Security Audit (AgentGuard)",
    "Fecha: {date}": "Date: {date}", "Alcance: {scope}": "Scope: {scope}",
    "## Resumen ejecutivo": "## Executive summary",
    "**Riesgo general: {risk}.**": "**Overall risk: {risk}.**",
    "| severidad | hallazgos |": "| severity | findings |",
    "## Hallazgos por severidad": "## Findings by severity",
    "- Detalle: {detail}": "- Detail: {detail}", "- Cómo arreglar: {fix}": "- How to fix: {fix}",
    "Sin hallazgos.": "No findings.",
    "## Revisión manual": "## Manual review",
    "> Para completar por quien audita. Lo automático no reemplaza esta parte.":
        "> To be completed by the auditor. The automated checks do not replace this part.",
    "- [ ] Hallazgos confirmados y descartados (por ID):": "- [ ] Findings confirmed and dismissed (by ID):",
    "- [ ] Permisos reales de cada servidor (tokens, carpetas, cuentas):":
        "- [ ] Actual permissions of each server (tokens, folders, accounts):",
    "- [ ] Origen y mantenedor de cada servidor (¿cambió de dueño o de repo?):":
        "- [ ] Origin and maintainer of each server (did the owner or repo change?):",
    "- [ ] Tools revisadas a mano (salida de tools/list):": "- [ ] Tools reviewed manually (tools/list output):",
    "- [ ] Skills de terceros leídas completas:": "- [ ] Third-party skills read in full:",
    "- [ ] Conclusión:": "- [ ] Conclusion:",
    "Auditor: ________ · Fecha: ________": "Auditor: ________ · Date: ________",
    "## Límites": "## Limitations",
    "- En un set ciego independiente (Skill-Inject, MIT: 34 ataques en 60 textos), las reglas solas marcaron "
    "como ALTO 2 de 34 ataques (6%); con `--deep` (Claude Haiku), 31 de 34 (91%). En 120 benignos, `--deep` "
    "dio 2 falsas alarmas ALTAS y 11 tuvieron algún aviso (9%). En 1170 SKILL.md reales, `--deep` marcó 30 "
    "como ALTO (2,6%, todos falsas alarmas al revisarlos a mano) y el 39% tuvo algún aviso. Es una sola "
    "medición; el modelo puede variar entre corridas. `--deep` envía el texto a Anthropic y necesita "
    "ANTHROPIC_API_KEY. Que no haya hallazgos no prueba que algo sea seguro.":
        "- On an independent blind set (Skill-Inject, MIT: 34 attacks in 60 texts), rules alone rated 2 of 34 "
        "attacks HIGH (6%); with `--deep` (Claude Haiku) 31 of 34 (91%). On 120 benign samples, `--deep` "
        "raised 2 HIGH false alarms and 11 got some notice (9%). On 1,170 real SKILL.md files, `--deep` rated "
        "30 HIGH (2.6%, all false alarms on manual review) and 39% got some notice. Single measurement; the "
        "model can vary between runs. `--deep` sends the text to Anthropic and needs ANTHROPIC_API_KEY. No "
        "findings does not prove something is safe.",
    "- `cve`, `trifecta` y `lock`/`verify` no dependen de las reglas de `scan` ni de `--deep`.":
        "- `cve`, `trifecta` and `lock`/`verify` don't depend on the `scan` rules or on `--deep`.",
    "- `trifecta` clasifica con una tabla de servidores conocidos y, si no están, con heurística por palabras; "
    "lo heurístico hay que confirmarlo a mano.":
        "- `trifecta` classifies with a table of known servers and, otherwise, with keyword heuristics; "
        "heuristic results must be confirmed manually.",
    "- `cve` solo encuentra vulnerabilidades publicadas en OSV.dev para paquetes con versión fija.":
        "- `cve` only finds vulnerabilities published on OSV.dev for packages with a pinned version.",
    "- No se ejecutó ningún servidor.": "- No server was executed.",
    "configs MCP instaladas": "installed MCP configs",
    "Reporte guardado en {path} ({n} hallazgo(s), riesgo {risk})":
        "Report saved to {path} ({n} finding(s), risk {risk})",
    # arreglos de scan (audit)
    "Confirma que solo explica dónde poner la llave y no le pide al modelo leerla.":
        "Confirm it only explains where to put the key and doesn't ask the model to read it.",
    "Revísalo ya: pide leer credenciales y sacarlas. Desinstálalo, cambia las llaves que menciona "
    "y repórtalo al autor o al registro.":
        "Review it now: it asks to read credentials and send them out. Uninstall it, rotate the keys it "
        "mentions and report it to the author or the registry.",
    "Quita el texto que pide ignorar instrucciones previas; una descripción legítima "
    "nunca lo necesita. Si viene de un tercero, no instales esa versión.":
        "Remove the text asking to ignore previous instructions; a legitimate description never needs it. "
        "If it comes from a third party, don't install that version.",
    "Elimina la orden de ocultarle cosas al usuario. Si viene de un tercero, trátalo como "
    "malicioso: desinstálalo y repórtalo.":
        "Remove the instruction to hide things from the user. If it comes from a third party, treat it as "
        "malicious: uninstall and report it.",
    "Elimina la orden de actuar sin avisar. Si viene de un tercero, trátalo como malicioso.":
        "Remove the instruction to act without telling the user. If it comes from a third party, treat it as malicious.",
    "Una tool no debe cambiar cómo se usan otras. Quita esa parte o desinstala el servidor.":
        "A tool must not change how other tools are used. Remove that part or uninstall the server.",
    "Quita imágenes con URLs armadas con datos y desactiva las imágenes remotas en el cliente.":
        "Remove images whose URLs are built from data and disable remote images in the client.",
    "Revisa por qué un parámetro recibe datos del contexto; limita el esquema a lo que la tool "
    "necesita.":
        "Check why a parameter receives context data; limit the schema to what the tool needs.",
    "Confirma que el dominio es del autor y que el envío hace falta; si no, quítalo.":
        "Confirm the domain belongs to the author and the send is needed; otherwise remove it.",
    "Quita etiquetas tipo <IMPORTANT> dirigidas al modelo; una descripción honesta no las necesita.":
        "Remove <IMPORTANT>-style tags aimed at the model; an honest description doesn't need them.",
    "Elimina comentarios HTML con instrucciones: el usuario no los ve, el modelo sí.":
        "Remove HTML comments containing instructions: the user can't see them, the model can.",
    "Decodifica el bloque y revísalo; si no es un dato necesario (imagen, certificado), quítalo.":
        "Decode the block and review it; if it isn't needed data (image, certificate), remove it.",
    "Elimina los caracteres invisibles (U+200B, tags U+E00xx, bidi) con un editor que los muestre.":
        "Remove the invisible characters (U+200B, U+E00xx tags, bidi) with an editor that shows them.",
    "Revisa el fragmento y decide si es legítimo.": "Review the snippet and decide whether it is legitimate.",
}

# Motivos de la tabla de servidores conocidos (trifecta/known.json)
EN.update({
    "lee y escribe archivos locales": "reads and writes local files",
    "lee repos git locales": "reads local git repos",
    "lee repos privados, trae issues y PRs escritos por terceros, y crea issues, comentarios y PRs":
        "reads private repos, brings in issues and PRs written by third parties, and creates issues, comments and PRs",
    "lee repos privados, trae issues de terceros, y crea issues y merge requests":
        "reads private repos, brings in third-party issues, and creates issues and merge requests",
    "trae cualquier página web; la URL que pide puede llevar datos hacia afuera":
        "fetches any web page; the URL it requests can carry data out",
    "trae y recorre páginas web; la URL que pide puede llevar datos hacia afuera":
        "fetches and crawls web pages; the URL it requests can carry data out",
    "trae resultados de búsqueda web": "brings in web search results",
    "trae datos de lugares de Google Maps": "brings in Google Maps place data",
    "navega páginas, llena formularios y visita cualquier URL": "browses pages, fills forms and visits any URL",
    "lee canales, trae mensajes de otras personas y publica mensajes":
        "reads channels, brings in messages from other people and posts messages",
    "lee páginas privadas, trae contenido que editan otros y escribe en Notion":
        "reads private pages, brings in content edited by others and writes to Notion",
    "lee correos privados, los correos que llegan son de terceros y envía correos":
        "reads private email, incoming mail comes from third parties, and sends email",
    "consulta una base de datos Postgres": "queries a Postgres database",
    "consulta una base de datos SQLite local": "queries a local SQLite database",
    "busca y lee archivos de Google Drive": "searches and reads Google Drive files",
    "guarda y lee un grafo de memoria local": "stores and reads a local memory graph",
    "lee una base de conocimiento privada en AWS": "reads a private knowledge base on AWS",
    "solo ayuda a razonar paso a paso; no lee ni envía datos": "only helps reason step by step; reads and sends no data",
    "solo da la hora y convierte zonas horarias": "only tells the time and converts time zones",
})


def t_note(note: str) -> str:
    """Notas del inventario MCP (algunas llevan el comando adentro)."""
    import re
    m = re.match(r"^comando '(.*)' no indica un paquete npm/PyPI$", note or "")
    if m:
        return t("comando '{cmd}' no indica un paquete npm/PyPI", cmd=m.group(1))
    return t(note)


def t_scope(label: str) -> str:
    """Etiquetas de alcance: 'Cursor · global', 'archivo · proyecto /ruta'."""
    parts = []
    for part in label.split(" · "):
        if part.startswith("proyecto "):
            parts.append(t("proyecto {where}", where=part[len("proyecto "):]))
        else:
            parts.append(t(part))
    return " · ".join(parts)


# scan --deep / audit --deep
EN.update({
    "Juicio semántico (deep)": "Semantic judgment (deep)",
    "Juicio semántico (deep): sin veredicto": "Semantic judgment (deep): no verdict",
    "motivo: {reason}": "reason: {reason}",
    "[fragmento no verificable]": "[snippet not verifiable]",
    "el modelo se negó a responder": "the model declined to answer",
    "respuesta cortada por max_tokens": "response cut off by max_tokens",
    "sin respuesta": "no response",
    "JSON inválido": "invalid JSON",
    "JSON con campos inesperados": "JSON with unexpected fields",
    "JSON con valores inválidos": "JSON with invalid values",
    "pedido rechazado: {msg}": "request rejected: {msg}",
    "límite de uso de la API": "API rate limit",
    "error de la API ({code})": "API error ({code})",
    "error de Ollama ({code})": "Ollama error ({code})",
    "Falta el SDK de Anthropic. Instálalo con: pip install agentguard-scan[deep]":
        "The Anthropic SDK is missing. Install it with: pip install agentguard-scan[deep]",
    "No hay credenciales de Anthropic (define ANTHROPIC_API_KEY)":
        "No Anthropic credentials (set ANTHROPIC_API_KEY)",
    "Clave de Anthropic inválida": "Invalid Anthropic key",
    "La clave de Anthropic no tiene permiso para este modelo": "The Anthropic key has no access to this model",
    "Modelo no encontrado: {model}": "Model not found: {model}",
    "Sin conexión con api.anthropic.com": "Cannot reach api.anthropic.com",
    "Ollama no tiene el modelo {model}. Descárgalo con: ollama pull {model}":
        "Ollama does not have the model {model}. Download it with: ollama pull {model}",
    "No se pudo conectar con Ollama en {host}": "Could not connect to Ollama at {host}",
    "Proveedor desconocido: {p} (usa anthropic u ollama)": "Unknown provider: {p} (use anthropic or ollama)",
    "Falta el valor de {flag}": "Missing value for {flag}",
    "--deep-fail-on solo acepta: high": "--deep-fail-on only accepts: high",
    "Las opciones --deep-* necesitan --deep": "The --deep-* options need --deep",
    "Con --deep-provider ollama hay que indicar el modelo: --deep-model <nombre>":
        "With --deep-provider ollama you must name the model: --deep-model <name>",
    "--deep solo funciona con scan y audit": "--deep only works with scan and audit",
    "--deep en audit necesita --skills <carpeta>": "--deep in audit needs --skills <folder>",
    "--deep enviará {n} elemento(s) de {files} archivo(s) ({kb:.0f} KB, ~{tokens} tokens) a {host} "
    "(modelo {model}). Costo estimado: {cost}. Antes de enviar se tapan las claves que parezcan reales.":
        "--deep will send {n} item(s) from {files} file(s) ({kb:.0f} KB, ~{tokens} tokens) to {host} "
        "(model {model}). Estimated cost: {cost}. Anything that looks like a real key is masked before sending.",
    "--deep juzgará {n} elemento(s) con Ollama en {host} (modelo {model}). No sale nada de esta máquina.":
        "--deep will judge {n} item(s) with Ollama at {host} (model {model}). Nothing leaves this machine.",
    "caracteres": "characters",
    "desconocido": "unknown",
    "--deep-dry-run: no se envió nada.": "--deep-dry-run: nothing was sent.",
    "Sin terminal interactiva no se envía nada. Agrega --deep-yes para confirmar.":
        "Without an interactive terminal nothing is sent. Add --deep-yes to confirm.",
    "¿Continuar? [s/N] ": "Continue? [y/N] ",
    "Cancelado: no se envió nada.": "Cancelled: nothing was sent.",
    "--deep no pudo correr: {err}": "--deep could not run: {err}",
    "deep ({model}): {calls} llamada(s), {findings} hallazgo(s), {high} ALTO(s), {none} sin veredicto. "
    "Tokens {tin}/{tout}, costo {cost}.":
        "deep ({model}): {calls} call(s), {findings} finding(s), {high} HIGH, {none} without verdict. "
        "Tokens {tin}/{tout}, cost {cost}.",
    "Se taparon {n} secreto(s) antes de enviar.": "{n} secret(s) were masked before sending.",
    "Lee la skill o tool completa y confirma si esa instrucción hace falta; si no, quítala o no la "
    "instales.": "Read the whole skill or tool and confirm whether that instruction is needed; if not, remove it or "
                 "don't install it.",
    "el texto se envió a {host}": "the text was sent to {host}",
    "corrió local con Ollama": "ran locally with Ollama",
    "- `--deep` usó {model} ({sent}). El juicio de un modelo no es determinista y puede "
    "equivocarse en ambos sentidos; confírmalo a mano.":
        "- `--deep` used {model} ({sent}). A model's judgment is not deterministic and can be wrong in both "
        "directions; confirm it by hand.",
})
