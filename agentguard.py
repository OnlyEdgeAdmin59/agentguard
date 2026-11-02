"""agentguard: seguridad para skills (SKILL.md) y herramientas MCP (JSON).

Uso:
  python agentguard.py scan   <carpeta> [--all]   detecta tool poisoning
                                                  (--all incluye node_modules, CHANGELOG, etc.)
  python agentguard.py lock   <carpeta>   guarda huellas en agentguard.lock.json
  python agentguard.py verify <carpeta>   alerta si algo cambió (rug pull)
  python agentguard.py cve [carpeta]      CVE conocidos de los servidores MCP instalados (OSV.dev)
Sale con código 1 si hay hallazgos ALTOS o cambios (útil para CI).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Submódulos (agentguard/cve/…) viven en la carpeta agentguard/ junto a este archivo.
__path__ = [str(Path(__file__).resolve().parent / "agentguard")]

# (nivel, nombre, patrón). Reglas simples; los filtros de contexto bajan falsas alarmas.
RULE_OVERRIDE = "Anula instrucciones previas"
RULE_HIDE = "Pide ocultar algo al usuario"
RULE_SECRET = "Menciona secretos"
RULE_SEND = "Envío de datos a URL externa"
RULE_COMMENT = "Instrucción oculta en comentario HTML"
RULE_B64 = "Bloque base64 largo"
RULE_INVISIBLE = "Caracteres invisibles (texto escondido)"
RULE_SHADOW = "Cambia cómo se usan otras herramientas (tool shadowing)"

URL = r"https?://"
RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ("ALTO", RULE_OVERRIDE,
     re.compile(r"ignore (all |any )?(previous|prior|above) (instructions|rules)", re.I)),
    # Lo mismo en español, portugués y francés.
    ("ALTO", RULE_OVERRIDE, re.compile(
        r"\b(?:ignora|ignorar|ignore|olvida|olvidar|omite|descarta)\s+(?:todas?\s+|cualquier\s+)?(?:las\s+|tus\s+|sus\s+)?"
        r"(?:instrucciones|reglas|indicaciones|[óo]rdenes)\s+(?:anteriores|previas|de arriba|del sistema)"
        r"|\bignor[ae]\s+(?:todas\s+)?(?:as\s+)?(?:instru[çc][õo]es|regras)\s+anteriores"
        r"|\bignore[zr]?\s+(?:toutes\s+)?(?:les\s+)?(?:instructions|r[èe]gles)\s+(?:pr[ée]c[ée]dentes|ant[ée]rieures)",
        re.I)),
    ("ALTO", RULE_HIDE,
     re.compile(r"(do not|don't|never) (tell|inform|mention|reveal|show)\b(?:[^.\n]|\.(?=\S)){0,40}(user|human)", re.I)),
    ("ALTO", RULE_HIDE, re.compile(
        r"\b(?:no|nunca|jam[aá]s)\s+(?:le\s+|les\s+|se\s+lo\s+)?(?:digas|informes|menciones|muestres|reveles|avises|cuentes|comentes)\b"
        r"(?:[^.\n]|\.(?=\S)){0,40}(?:usuario|humano|cliente)"
        r"|\bsin\s+(?:avisar|decir|informar|contar|notificar|preguntar)(?:le|les)?\s+(?:nada\s+)?(?:al|a\s+los)\s+usuarios?"
        r"|\bsin\s+que\s+(?:el|los)\s+usuarios?\s+(?:lo\s+|se\s+)?(?:sepa|note|entere|vea)n?"
        r"|\bn[ãa]o\s+(?:conte|diga|informe|mostre|mencione)\b[^.\n]{0,40}usu[áa]rio"
        r"|\bne\s+(?:le\s+|lui\s+)?(?:dis|dites|mentionne[sz]?|montre[sz]?)\s+(?:pas|rien)\b[^.\n]{0,40}utilisateur",
        re.I)),
    ("MEDIO", RULE_SECRET,
     re.compile(r"(\.ssh|id_rsa|\.env\b|\.aws/credentials|api[_-]?key|private key|mcp\.json)", re.I)),
    # Envío real: comandos/código HTTP, o una orden "send X to https://". Nada de "postcss" ni links markdown.
    ("MEDIO", RULE_SEND, re.compile(
        r"curl\b[^\n]{0,120}(-X\s*POST|--data|-d\s|-F\s|--upload-file)[^\n]{0,120}" + URL
        + r"|curl\b[^\n]{0,120}" + URL + r"[^\n]{0,120}(-X\s*POST|--data|-d\s|-F\s|--upload-file)"
        + r"|\b(requests|httpx|axios|session|client)\.(post|put)\(\s*f?[\"'`]" + URL
        + r"|fetch\(\s*[\"'`]" + URL + r"[^)]{0,200}method\s*:\s*[\"']?(POST|PUT)"
        + r"|\b(send|upload|forward|exfiltrate|post|transmit)\b(?:[^.\n]|\.(?=\S)){0,60}\bto\b\s*[`\"'(<]?" + URL
        + r"|\b(env[ií]a(?:lo|la|los|las|r)?|env[ií]e(?:lo|la)?|manda(?:lo|la|r)?|sube(?:lo|la)?|subir|reenv[ií]a(?:lo|la)?"
        r"|transmite|exfiltra|envoie[sz]?|envi[ae]-?(?:o|a)?)\b(?:[^.\n]|\.(?=\S)){0,60}\b(?:a|para|à|al)\b\s*[`\"'(<]?" + URL,
        re.I)),
    ("MEDIO", "Etiquetas de urgencia para el modelo",
     re.compile(r"<\s*(important|system|secret|instructions?)\s*>", re.I)),
    ("MEDIO", RULE_COMMENT, re.compile(r"<!--.*?-->", re.S)),
    ("MEDIO", RULE_B64, re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")),
    ("ALTO", RULE_INVISIBLE,
     re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\U000e0000-\U000e007f]")),
    # Tool shadowing: la descripci\u00f3n de una tool cambia c\u00f3mo el agente usa OTRAS tools.
    ("ALTO", RULE_SHADOW, re.compile(
        r"\b(?:when(?:ever)?|each time|every time|any time)\b[^.\n]{0,50}?\b(?!(?:this|the|a|that|same|it)\b)"
        r"[`'\"]?[\w-]+[`'\"]?\s+tool\b[^.\n]{0,25}?\b(?:is (?:used|called|invoked|run)|returns|runs|you (?:call|use|invoke|run))"
        r"|\bregardless of (?:what|whatever) the user (?:said|says|asked|asks|wants|requested|typed)"
        r"|\b(?:first|also|always)\s+(?:call|use|invoke)\s+this tool\b[^.\n]{0,40}\bwith\b[^.\n]{0,30}"
        r"\b(?:history|conversation|messages|contents|output|credentials|files?)\b"
        r"|\b(?:pass|send|forward|copy|include|append)\s+(?:those |these |the |its |their |all )?"
        r"(?:contents?|outputs?|results?|history|messages|responses?)\b[^.\n]{0,30}\bto this tool"
        r"|\b(?:do not|don't|never)\s+use\s+the\s+(?:official\s+|built-in\s+|original\s+|other\s+)?[`'\"]?[\w-]+[`'\"]?\s+"
        r"(?:tool|server|integration)\b[^.\n]{0,80}\b(?:deprecated|broken|has a bug|use this tool)"
        r"|\b(?:always|also|silently|secretly)\s+(?:add|include|cc|bcc|copy)\b[^.\n]{0,40}[\w.+-]+@[\w-]+\.[a-z]{2,}",
        re.I)),
]

# Comentario HTML que le habla al modelo (lo demás son comentarios normales y se ignoran).
COMMENT_ORDER = re.compile(
    r"ignore (all |any )?(previous|prior|above)|disregard|when (asked|the user|a user|someone)"
    r"|\brecommend\b|tell the user|\bassistant\b|system prompt|as an ai|always (respond|answer|say)",
    re.I)
# Señales de que el texto cita un ataque como ejemplo (documentación de seguridad).
QUOTED_CONTEXT = re.compile(
    r"example|e\.g\.|such as|attack|injection|malicious|adversar|payload|phrase|detect|pattern|jailbreak"
    r"|ejemplo|p\. ?ej|ataque|inyecci|malicios|frase|patr[oó]n",
    re.I)
ADDRESS = re.compile(r"https?://\S+|[\w.+-]+@[\w-]+(\.[\w-]+)+")
# Ocultar algo solo es grave si lo oculto es una acción o un secreto.
HIDE_DANGER = re.compile(
    r"send|sent|upload|delet|run|execut|install|download|key|token|password|credential|secret|\.ssh|\.env|file"
    r"|\benv[ií][aeo]|\bsub(?:ir|e|i[oó])\b|borr|elimin|ejecut|instal|descarg|clave|contrase|senha|archivo|fichero|arquivo|fichier",
    re.I)


@dataclass
class Finding:
    level: str
    rule: str
    source: str
    line: int
    snippet: str
    context: str = ""  # línea completa, para reglas que necesitan ver más que el fragmento


def line_at(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return text[start:end if end != -1 else len(text)]


def is_emoji(ch: str) -> bool:
    return ord(ch) >= 0x2190  # flechas, símbolos, emojis, selectores de variación, tonos de piel


def is_quoted(before: str) -> bool:
    """El match está entre comillas: abre justo antes, o hay una comilla abierta sin cerrar.
    Un apóstrofo suelto ('sidenote', don't) no cuenta: antes eso bajaba ataques reales a MEDIO."""
    stripped = before.rstrip()
    if stripped and stripped[-1] in "\"'`«“":
        return True
    return before.count('"') % 2 == 1 or before.count("`") % 2 == 1 or before.count("“") > before.count("”") \
        or before.count("«") > before.count("»")


def adjust(name: str, level: str, m: re.Match[str], text: str) -> str | None:
    """Ajusta el nivel según el contexto. None = descartar (falsa alarma conocida)."""
    if name == RULE_INVISIBLE:
        ch, i = m.group(0), m.start()
        if ch == "\ufeff" and i == 0:
            return None  # BOM al inicio del archivo
        if ch == "\u200d" and 0 < i < len(text) - 1 and is_emoji(text[i - 1]) and is_emoji(text[i + 1]):
            return None  # une emojis: 👨‍💻
        return level
    if name == RULE_COMMENT:
        return "ALTO" if COMMENT_ORDER.search(m.group(0)) else None
    if name == RULE_B64:
        token_start = max(text.rfind(c, 0, m.start()) for c in " \n\t(\"'") + 1
        if "://" in text[token_start:m.start()]:
            return None  # parte de una URL (playgrounds, badges)
        return level
    if name in (RULE_OVERRIDE, RULE_HIDE, RULE_SHADOW):
        line = line_at(text, m.start())
        prose = ADDRESS.sub(" ", line)  # "attacker@evil.io" o una URL no son documentación de seguridad
        if is_quoted(line[:m.start() - text.rfind("\n", 0, m.start()) - 1]) or QUOTED_CONTEXT.search(prose):
            return "MEDIO"  # cita un ataque como ejemplo
        if name == RULE_HIDE and not HIDE_DANGER.search(line):
            return "MEDIO"  # UX normal: "never show raw errors to the user"
        return level
    return level


def scan_text(text: str, source: str) -> list[Finding]:
    findings = []
    for level, name, pattern in RULES:
        for m in pattern.finditer(text):
            final = adjust(name, level, m, text)
            if final is None:
                continue
            line = text.count("\n", 0, m.start()) + 1
            snippet = m.group(0).replace("\n", " ")[:80]
            ctx_start = text.rfind("\n", 0, m.start()) + 1
            ctx_end = text.find("\n", m.end())
            context = text[ctx_start:ctx_end if ctx_end != -1 else len(text)]  # todas las líneas del match
            findings.append(Finding(final, name, source, line, snippet, context))
    return findings


NEAR_LINES = 5


LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")
AUTH_HEADER = re.compile(r"authorization|bearer|x-api-key|api-key\s*[:=]|headers\s*[=:{]|-H\s", re.I)


def same_vendor(secret: Finding, send: Finding) -> bool:
    """La key va como credencial a su propio proveedor (FAL_KEY → fal.run) o a localhost = uso normal."""
    host = re.search(r"https?://([^/\s\"'`)]+)", send.context)
    if not host:
        return False
    h = host.group(1).lower()
    if h.startswith(LOCAL_HOSTS):
        return True
    names = re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_(?:API_?KEY|KEY|TOKEN|SECRET)\b", secret.context + " " + send.context)
    words = {w for n in names for w in n.lower().split("_") if len(w) > 2 and w not in ("api", "key", "apikey", "token", "secret")}
    if any(w in h for w in words):
        return True
    # credencial en un header de autenticación (así se usa una API), no en el cuerpo del envío
    return bool(AUTH_HEADER.search(secret.context)) and not re.search(r"\.ssh|id_rsa|credentials|private key", secret.context, re.I)


def escalate(findings: list[Finding]) -> list[Finding]:
    """Secreto + envío externo a ≤5 líneas en la misma fuente = ALTO (salvo que vaya a su propio proveedor)."""
    secrets = [f for f in findings if f.rule == RULE_SECRET]
    sends = [f for f in findings if f.rule == RULE_SEND]
    extra, seen = [], set()
    for s in secrets:
        for d in sends:
            if d.source == s.source and abs(d.line - s.line) <= NEAR_LINES and not same_vendor(s, d):
                key = (s.source, min(s.line, d.line))
                if key not in seen:
                    seen.add(key)
                    extra.append(Finding("ALTO", "Secreto + envío externo (posible robo)", s.source, s.line,
                                         f"{s.snippet} → {d.snippet}"[:80]))
    return findings + extra


def texts_from_mcp_json(data: object, path: str = "") -> list[tuple[str, str]]:
    """Extrae description/inputSchema de una lista de herramientas MCP."""
    out: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            sub = f"{path}.{key}" if path else key
            if key in ("description", "title") and isinstance(value, str):
                out.append((sub, value))
            else:
                out.extend(texts_from_mcp_json(value, sub))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            out.extend(texts_from_mcp_json(item, f"{path}[{i}]"))
    return out


def scan_file(path: Path) -> list[Finding]:
    if path.stat().st_size > MAX_BYTES:
        return [Finding("MEDIO", "Archivo demasiado grande, no revisado", str(path), 0, "")]
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            pieces = texts_from_mcp_json(json.loads(text))
        except json.JSONDecodeError:
            return [Finding("MEDIO", "JSON inválido", str(path), 0, "")]
        return [f for src, t in pieces for f in scan_text(t, f"{path}::{src}")]
    return scan_text(text, str(path))


LOCK_NAME = "agentguard.lock.json"
MAX_BYTES = 2_000_000  # archivos más grandes se reportan, no se leen
IN_GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"


def annotate(level: str, file: str, line: int, msg: str) -> None:
    """En GitHub Actions marca el hallazgo en la línea del PR."""
    if not IN_GITHUB:
        return
    kind = "error" if level == "ALTO" else "warning"
    loc = f"file={file.split('::')[0]},line={max(line, 1)}"
    print(f"::{kind} {loc},title=agentguard {level}::{msg}")


SKIP_DIRS = {"node_modules", ".git", ".github", ".trash", "fixtures", "__pycache__", ".venv", "venv", "site-packages"}
SKIP_FILES = ("changelog", "license", "history", "third_party_notices")


def skipped(path: Path, base: Path) -> bool:
    parts = path.relative_to(base).parts
    return any(p in SKIP_DIRS for p in parts[:-1]) or path.name.lower().startswith(SKIP_FILES)


def collect(target: Path, include_all: bool = False) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(
        p for p in target.rglob("*")
        if p.suffix.lower() in (".md", ".json") and p.name != LOCK_NAME
        and not p.is_symlink() and p.is_file()
        and (include_all or not skipped(p, target))
    )


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprints(target: Path) -> dict[str, str]:
    """Una huella por archivo y, en MCP, una por herramienta (name+description+schema)."""
    base = target if target.is_dir() else target.parent
    prints: dict[str, str] = {}
    for path in collect(target):
        rel = path.relative_to(base).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        prints[rel] = sha(text)
        if path.suffix.lower() == ".json":
            try:
                tools = json.loads(text).get("tools", [])
            except (json.JSONDecodeError, AttributeError):
                continue
            for tool in tools if isinstance(tools, list) else []:
                if isinstance(tool, dict) and "name" in tool:
                    key = {k: tool.get(k) for k in ("name", "description", "inputSchema")}
                    prints[f"{rel}::tool:{tool['name']}"] = sha(json.dumps(key, sort_keys=True))
    return prints


def lock_path(target: Path) -> Path:
    return (target if target.is_dir() else target.parent) / LOCK_NAME


def cmd_scan(target: Path, include_all: bool = False) -> int:
    files = collect(target, include_all)
    findings = escalate([f for p in files for f in scan_file(p)])
    for f in findings:
        print(f"[{f.level}] {f.rule} — {f.source}:{f.line}  «{f.snippet}»")
        annotate(f.level, f.source, f.line, f"{f.rule}: {f.snippet}")
    altos = sum(f.level == "ALTO" for f in findings)
    hint = "" if include_all else " (excluye node_modules, CHANGELOG, LICENSE…; usá --all para incluirlos)"
    print(f"\n{len(files)} archivo(s), {len(findings)} hallazgo(s), {altos} ALTO(s){hint}")
    return 1 if altos else 0


def cmd_lock(target: Path) -> int:
    prints = fingerprints(target)
    lock_path(target).write_text(json.dumps(prints, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Guardadas {len(prints)} huella(s) en {lock_path(target)}")
    return 0


def cmd_verify(target: Path) -> int:
    try:
        old = json.loads(lock_path(target).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("No hay lock. Corré primero: python agentguard.py lock <carpeta>")
        return 2
    new = fingerprints(target)
    changed = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    for k in changed:
        print(f"[ALTO] CAMBIÓ desde que lo aprobaste: {k}")
        annotate("ALTO", str(lock_path(target).parent / k), 1, "Cambió desde que se aprobó (posible rug pull)")
    for k in added:
        print(f"[MEDIO] Nuevo, sin aprobar: {k}")
    for k in removed:
        print(f"[INFO] Eliminado: {k}")
    if not (changed or added or removed):
        print("Todo igual que cuando lo aprobaste.")
    return 1 if changed or added else 0


COMMANDS = {"scan": cmd_scan, "lock": cmd_lock, "verify": cmd_verify}


def main(argv: list[str]) -> int:
    # Windows redirige a archivo en cp1252: forzar UTF-8 y no romper por caracteres raros
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    if len(argv) >= 2 and argv[1] == "cve":
        from agentguard.cve import cmd_cve  # import tardío: scan/lock/verify no lo necesitan
        return cmd_cve(argv[2:])
    include_all = "--all" in argv
    argv = [a for a in argv if a != "--all"]
    if len(argv) == 2 and argv[1] not in COMMANDS:  # compatibilidad: scan por defecto
        argv = [argv[0], "scan", argv[1]]
    if len(argv) != 3 or argv[1] not in COMMANDS:
        print(__doc__)
        return 2
    if argv[1] == "scan":
        return cmd_scan(Path(argv[2]), include_all)
    return COMMANDS[argv[1]](Path(argv[2]))


def run() -> None:
    """Punto de entrada del comando `agentguard` instalado con pip."""
    sys.exit(main(sys.argv))


if __name__ == "__main__":
    run()
