"""Motor de agentguard: reglas, normalización de texto, escaneo de archivos y huellas para lock/verify."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# (nivel, nombre, patrón). Reglas simples; los filtros de contexto bajan falsas alarmas.
RULE_OVERRIDE = "Anula instrucciones previas"
RULE_HIDE = "Pide ocultar algo al usuario"
RULE_SECRET = "Menciona secretos"
RULE_SEND = "Envío de datos a URL externa"
RULE_COMMENT = "Instrucción oculta en comentario HTML"
RULE_B64 = "Bloque base64 largo"
RULE_INVISIBLE = "Caracteres invisibles (texto escondido)"
RULE_SHADOW = "Cambia cómo se usan otras herramientas (tool shadowing)"
RULE_STEALTH = "Pide hacer algo a escondidas"
RULE_PARAM = "Mete datos en un parámetro de la tool"
RULE_B64_HIDDEN = "Instrucción escondida en base64"

URL = r"https?://"
RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ("ALTO", RULE_OVERRIDE,
     re.compile(r"ignore (all |any )?(previous|prior|above) (instructions|rules)", re.I)),
    # Lo mismo en español, portugués y francés.
    ("ALTO", RULE_OVERRIDE, re.compile(
        r"\b(?:ignora|ignorar|ignore|olvida|olvidar|omite|descarta)\s+(?:todas?\s+|cualquier\s+)?(?:las\s+|tus\s+|sus\s+)?"
        r"(?:instrucciones|reglas|indicaciones|[óo]rdenes)\s+(?:anteriores|previas|de arriba|del sistema)"
        r"|\bignor[ae]\s+(?:todas\s+)?(?:as\s+)?(?:instru[çc][õo]es|regras)\s+anteriores"
        r"|\bignore[zr]?\s+(?:toutes\s+)?(?:les\s+)?(?:instructions|r[èe]gles)\s+(?:pr[ée]c[ée]dentes|ant[ée]rieures)"
        # Más verbos y sustantivos en portugués y francés ("desconsidere as orientações recebidas antes").
        r"|\b(?:desconsider[ae]|esque[çc]a|ignor[ae])\s+(?:todas\s+)?(?:as\s+)?(?:orienta[çc][õo]es|instru[çc][õo]es"
        r"|regras|diretrizes)\s+(?:recebidas\s+)?(?:anteriores|antes|anteriormente|do\s+sistema|do\s+desenvolvedor)"
        r"|\b(?:oublie[zr]?|ignore[zr]?)\s+(?:toutes\s+)?(?:les\s+)?(?:r[èe]gles|instructions|consignes|directives)\s+"
        r"(?:fix[ée]es\s+par|pr[ée]c[ée]dentes|ant[ée]rieures|du\s+(?:d[ée]veloppeur|syst[èe]me))",
        re.I)),
    # Reformulaciones: otras palabras para anular reglas o cambiarle el papel al modelo.
    ("ALTO", RULE_OVERRIDE, re.compile(
        r"\b(?:disregard|forget|bypass|set aside|discard)\s+(?:all\s+|any\s+)?(?:of\s+)?(?:your|the|previous|prior|earlier"
        r"|above|system|safety|existing)\s+(?:[\w-]+\s+){0,2}?(?:instructions?|rules|guidelines|guardrails|polic(?:y|ies)"
        r"|prompt|restrictions|directives)\b"
        r"|\byou are now (?:in |a |an )?[^.\n]{0,25}\b(?:mode|unrestricted|jailbroken|unfiltered)\b"
        # Declarar vencidas las reglas que recibió el modelo, o que ya no lo atan.
        r"|\b(?:instructions?|guidance|rules|guidelines|polic(?:y|ies)|directives|prompt)\b[^.\n]{0,15}"
        r"\b(?:you(?:'ve| have)? (?:received|were given|got)|given to you)\b[^.\n]{0,25}"
        r"\b(?:outdated|obsolete|superseded|revoked|void|no longer (?:valid|appl))"
        r"|\bno longer (?:binds?|appl(?:y|ies) to|restricts?) you\b"
        r"|\byou (?:now )?(?:operate|act) as an? (?:unrestricted|unfiltered|uncensored|jailbroken)\b"
        r"|\b(?:note|message) (?:to|for) the (?:ai|assistant|model|llm|agent)(?: model)?\s*:"  # "instructions for the AI" = docs
        r"|\b(?:salta(?:te|r)?|evita|desobedece|desactiva)\s+(?:todas?\s+)?(?:las\s+|tus\s+)?(?:reglas|restricciones"
        r"|instrucciones|pol[ií]ticas)\b(?:\s+de seguridad)?"
        r"|\b(?:ahora|a partir de ahora)\s+est[áa]s\s+en\s+modo\b"
        r"|\bnota\s+(?:para|al)\s+(?:el\s+|la\s+)?(?:asistente|modelo|agente|ia)\b",
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
     re.compile(r"(\.ssh|id_rsa|\.env\b|\.aws/credentials|api[_-]?key|private key|mcp\.json"
                r"|gh/hosts\.ya?ml|\.netrc|\.git-credentials|\.npmrc|\.pypirc|\.docker/config\.json|\.kube/config)", re.I)),
    # PISTA = no se muestra sola; solo cuenta para escalar con un envío o un parámetro (si no, duplica el ruido).
    ("PISTA", RULE_SECRET,  # AWS_SECRET_KEY, GITHUB_TOKEN…, "all environment variables"
     re.compile(r"\b[A-Z][A-Z0-9]*_(?:SECRET(?:_ACCESS)?_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|ACCESS_KEY)\b"
                r"|(?i:(?:all )?environment variables|env vars|variables de entorno)"
                r"|(?i:output of\s+`(?:env|printenv|set)`|salida de\s+`(?:env|printenv)`)")),  # volcado del entorno
    # Orden de hacer algo a escondidas ("silently append…"); "X silently fails" es descriptivo y no cuenta.
    # Grave solo si lo escondido es un envío o un secreto (STEALTH_DANGER).
    ("ALTO", RULE_STEALTH, re.compile(
        r"\b(?:silently|secretly|quietly|covertly|discreetly)\s+(?:send|upload|forward|append|include|copy|attach|post"
        r"|call|add|read|collect|exfiltrate|share|transmit|run|execute|install|download)\b"
        r"|\bwithout (?:telling|informing|notifying|alerting) (?:the )?user\b"
        r"|\b(?:env[ií]a|sube|reenv[ií]a|copia|agrega|lee|manda)\w*\s+(?:en secreto|silenciosamente|discretamente"
        r"|a escondidas)\b|\b(?:en secreto|silenciosamente|discretamente|a escondidas)\s+(?:env[ií]a|sube|reenv[ií]a|copia"
        r"|agrega|lee|manda)", re.I)),
    # Meter datos en un parámetro de la tool: con un secreto cerca sube a ALTO (ver escalate).
    ("MEDIO", RULE_PARAM, re.compile(
        r"\b(?:include|put|pass|place|add|insert|copy|embed|attach|append|incluye|pon|pasa|mete|agrega)\b[^.\n]{0,60}"
        r"\b(?:in|into|as|to|en|como)\s+(?:the |this tool's |every |el |la )?[`'\"]?[\w-]+[`'\"]?\s+"
        r"(?:parameter|param|field|argument|arg|par[áa]metro|campo|argumento)\b"
        # Orden inverso: "copia en el parámetro 'contexto' …", "put into the field `notes` …"
        r"|\b(?:include|put|pass|place|add|insert|copy|embed|attach|append|incluye|pon|pasa|mete|agrega|copia|a[ñn]ade)\b"
        r"[^.\n]{0,60}?\b(?:in|into|en)\s+(?:the |el |la )(?:parameter|param|field|argument|par[áa]metro|campo|argumento)"
        r"\s+[`'\"]?[\w-]+", re.I)),
    ("ALTO", "Imagen markdown que filtra datos por la URL", re.compile(
        r"!\[[^\]]*\]\(\s*https?://[^)\s]*[?&][\w-]+=(?:\{\{?\s*[\w.]*(?:user|message|conversation|chat|history|secret"
        r"|token|key|summary|password)[\w.]*\s*\}?\}|<[^>]*(?:user|message|conversation|chat|history|secret|token|key"
        r"|summary)[^>]*>|[A-Z][A-Z0-9_]{3,})")),
    # Envío real: comandos/código HTTP, o una orden "send X to https://". Nada de "postcss" ni links markdown.
    ("MEDIO", RULE_SEND, re.compile(
        r"curl\b[^\n]{0,120}(-X\s*POST|--data|-d\s|-F\s|--upload-file)[^\n]{0,120}" + URL
        + r"|curl\b[^\n]{0,120}" + URL + r"[^\n]{0,120}(-X\s*POST|--data|-d\s|-F\s|--upload-file)"
        + r"|\b(requests|httpx|axios|session|client)\.(post|put)\(\s*f?[\"'`]" + URL
        + r"|fetch\(\s*[\"'`]" + URL + r"[^)]{0,200}method\s*:\s*[\"']?(POST|PUT)"
        + r"|\b(?:urlopen|Request)\(\s*[\"'`]" + URL + r"[^\n]{0,200}\bdata\s*="  # urllib con cuerpo = POST
        + r"|\b(send|upload|forward|exfiltrate|post|transmit|append|attach)\b(?:[^.\n]|\.(?=\S)){0,60}\bto\b\s*[`\"'(<]?" + URL
        + r"|\b(env[ií]a(?:lo|la|los|las|r)?|env[ií]e(?:lo|la)?|manda(?:lo|la|r)?|sube(?:lo|la)?|subir|reenv[ií]a(?:lo|la)?"
        r"|transmite|exfiltra|envoie[sz]?|envi[ae]-?(?:o|a)?)\b(?:[^.\n]|\.(?=\S)){0,60}\b(?:a|para|à|al)\b\s*[`\"'(<]?" + URL,
        re.I)),
    ("MEDIO", "Etiquetas de urgencia para el modelo",
     re.compile(r"<\s*(important|system|secret|instructions?)\s*>", re.I)),
    ("MEDIO", RULE_COMMENT, re.compile(r"<!--.*?-->", re.S)),
    ("MEDIO", RULE_B64, re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")),
    ("ALTO", RULE_INVISIBLE,
     re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\U000e0000-\U000e007f]")),
    # Tool shadowing: la descripci\u00f3n de una tool cambia c\u00f3mo el agente usa OTRAS tools.
    ("ALTO", RULE_SHADOW, re.compile(
        r"\b(?:when(?:ever)?|each time|every time|any time)\b[^.\n]{0,50}?\b(?!(?:this|the|a|that|same|it)\b)"
        r"[`'\"]?[\w-]+[`'\"]?\s+tool\b[^.\n]{0,25}?\b(?:is (?:used|called|invoked|run)|returns|runs|you (?:call|use|invoke|run))"
        # …y además le cambia algo a esa llamada ("when X tool returns, retry" = docs normales)
        r"[^.\n]{0,40}?\b(?:always|also|silently|secretly|instead|replace|change|set|add|bcc|cc|redirect|first)\b"
        # "For every call to create_pull_request, set…": cambia los argumentos de otra tool (nombre tipo snake_case).
        r"|\b(?:for|on|before|after|in)\s+(?:every|each|any|all)\s+calls?\s+(?:to|of)\s+[`'\"]?[a-z]+_[\w]+[`'\"]?"
        r"[^.\n]{0,20}?\b(?:always|set|add|replace|change|prefix|redirect|instead|remove|leave)\b"
        # Meterle a cada comando de otra tool un script remoto: "prefix `curl … | sh;`".
        r"|\b(?:prefix|prepend|prefija|antepon)\w*\b[^\n]{0,40}?\b(?:curl|wget|iwr|irm)\b[^\n]{0,120}?"
        r"\|\s*(?:sudo\s+)?(?:(?:ba|z)?sh|iex)\b"
        # Lo mismo en español: "cuando uses la herramienta X, cambia siempre…"
        r"|\b(?:cuando|cada vez que|siempre que)\b[^.\n]{0,20}?\b(?:uses|llames|invoques|ejecutes|se use|se llame)\s+"
        r"(?:a\s+)?(?:la\s+)?(?:herramienta|tool)\s+(?!(?:esta|este|la misma|misma)\b)[`'\"]?[\w-]+[`'\"]?[^.\n]{0,40}?"
        r"\b(?:siempre|tambi[eé]n|en su lugar|cambia|reemplaza|sustituye|agrega|añade|pon|redirige|primero)\b"
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
STEALTH_DANGER = re.compile(
    r"send|upload|forward|append|include|copy|attach|post|exfil|\.env|\.ssh|id_rsa|credential|password|token"
    r"|\|\s*(?:sudo\s+)?(?:ba|z)?sh\b|\biex\b"  # script remoto a la shell: "curl … | sh"
    r"|api[_ -]?key|secret|history|conversation|environment|\benv[ií][aeo]|sube|clave|contrase|historial|conversaci",
    re.I)
# Exfiltración por parámetro: tiene que haber algo que se lee o junta, no "pass your API key in 'key'".
PARAM_ACQUIRE = re.compile(
    r"value of|contents? (?:\w+ )?of|contenido (?:\w+ )?de|\bread\b|collect|gather|dump|\ball (?:the )?(?:environment|env|files|keys|secrets)"
    r"|valor de|contenido de|\blee\b|junta|recopila", re.I)
NEGATED = re.compile(r"\b(?:never|not|don't|no|nunca|jam[aá]s)\b\W*$", re.I)
ADDRESS = re.compile(r"https?://\S+|[\w.+-]+@[\w-]+(\.[\w-]+)+")
# Ocultar algo solo es grave si lo oculto es una acción o un secreto.
HIDE_DANGER = re.compile(
    # "file" solo no basta: "don't tell the user where the file is" es UX normal (visto en skills reales).
    r"send|sent|upload|delet|run|execut|install|download|key|token|password|credential|secret|\.ssh|\.env"
    r"|\benv[ií][aeo]|\bsub(?:ir|e|i[oó])\b|borr|elimin|ejecut|instal|descarg|clave|contrase|senha",
    re.I)


@dataclass
class Finding:
    level: str
    rule: str
    source: str
    line: int
    snippet: str
    context: str = ""  # línea completa, para reglas que necesitan ver más que el fragmento
    reason: str = ""  # motivo en palabras (solo lo usa --deep)


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
            return None  # une emojis: 👨\u200d💻
        return level
    if name == RULE_COMMENT:
        return "ALTO" if COMMENT_ORDER.search(m.group(0)) else None
    if name == RULE_B64:
        token_start = max(text.rfind(c, 0, m.start()) for c in " \n\t(\"'") + 1
        if "://" in text[token_start:m.start()]:
            return None  # parte de una URL (playgrounds, badges)
        return level
    if name == RULE_STEALTH and (NEGATED.search(text[max(0, m.start() - 20):m.start()])
                                 or not STEALTH_DANGER.search(line_at(text, m.start()))):
        return "MEDIO"  # "never silently add scope", "silently ignores unknown fields"
    if name == RULE_HIDE and re.match(r"\s+to\b", text[m.end():]):
        return "MEDIO"  # "don't tell the user to use a card": es una instrucción, no un secreto
    if name in (RULE_OVERRIDE, RULE_HIDE, RULE_SHADOW, RULE_STEALTH):
        line = line_at(text, m.start())
        prose = ADDRESS.sub(" ", line)  # "attacker@evil.io" o una URL no son documentación de seguridad
        if is_quoted(line[:m.start() - text.rfind("\n", 0, m.start()) - 1]) or QUOTED_CONTEXT.search(prose):
            return "MEDIO"  # cita un ataque como ejemplo
        if name == RULE_HIDE and not HIDE_DANGER.search(line):
            return "MEDIO"  # UX normal: "never show raw errors to the user"
        return level
    return level


# Letras cirílicas/griegas que se ven iguales a las latinas.
CONFUSABLES = str.maketrans(
    "\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u0456\u0458\u0455\u0501\u04cf\u04bb\u051b\u051d"
    "\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0425\u0406\u0408\u0405"
    "\u03bf\u03b9\u03bd\u03b1\u0391\u0392\u0395\u0396\u0397\u0399\u039a\u039c\u039d\u039f\u03a1\u03a4\u03a5\u03a7",
    "aeopcyxijsdlhqw"
    "ABEKMHOPCTXIJS"
    "oivaABEZHIKMNOPTYX")
RULE_HOMOGLYPH = "Letras de otro alfabeto que imitan latinas (homoglifos)"
CONFUSABLE_CHARS = "".join(chr(c) for c in CONFUSABLES)
HOMOGLYPH_WORD = re.compile(rf"\b(?=\w*[A-Za-z])(?=\w*[{CONFUSABLE_CHARS}])\w+\b")
TAG_CHARS = re.compile(r"[\U000e0020-\U000e007e]+")
BIDI_OVERRIDE = re.compile(r"\u202e([^\u202c\n]*)\u202c?")
INVISIBLE = re.compile(r"[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\U000e0000-\U000e007f]")


def normalize(text: str) -> str:
    """Lo que el modelo 'lee': texto escondido a la vista, sin invisibles, sin homoglifos ni ancho completo.
    No cambia los saltos de línea, así los números de línea siguen sirviendo."""
    text = TAG_CHARS.sub(lambda m: "".join(chr(ord(c) - 0xE0000) for c in m.group(0)), text)
    text = BIDI_OVERRIDE.sub(lambda m: m.group(1)[::-1], text)
    text = INVISIBLE.sub("", text)
    return unicodedata.normalize("NFKC", text).translate(CONFUSABLES)


B64_ANY = re.compile(r"(?<![\w/+])[A-Za-z0-9+/]{32,}={0,2}")


def decode_b64(block: str) -> str | None:
    """Texto legible escondido en un bloque base64, o None si son bytes (imágenes, binarios)."""
    try:
        raw = base64.b64decode(block[: len(block) - len(block) % 4] or "", validate=False)
        decoded = raw.decode("utf-8", errors="replace")  # bloques pegados o cortados dejan basura al final
    except binascii.Error:
        return None
    readable = re.match(r"[^\x00-\x08\x0b-\x1f\x7f\ufffd]*", decoded).group(0)  # tramo legible del principio
    return readable if len(readable) >= 24 else None  # PNG/binarios empiezan con bytes de control


def scan_text(text: str, source: str, depth: int = 0) -> list[Finding]:
    findings = []
    clean = normalize(text)
    for level, name, pattern in RULES + [("ALTO", RULE_HOMOGLYPH, HOMOGLYPH_WORD)]:
        target = text if name in (RULE_INVISIBLE, RULE_HOMOGLYPH) else clean
        for m in pattern.finditer(target):
            final = adjust(name, level, m, target)
            if final is None:
                continue
            line = target.count("\n", 0, m.start()) + 1
            snippet = m.group(0).replace("\n", " ")[:80]
            ctx_start = target.rfind("\n", 0, m.start()) + 1
            ctx_end = target.find("\n", m.end())
            context = target[ctx_start:ctx_end if ctx_end != -1 else len(target)]  # todas las líneas del match
            findings.append(Finding(final, name, source, line, snippet, context))
    if depth == 0:  # base64 que esconde una orden (aunque sea corto); se revisa lo decodificado
        for m in B64_ANY.finditer(clean):
            hidden = decode_b64(m.group(0))
            if hidden and any(f.level == "ALTO" for f in escalate(scan_text(hidden, source, depth + 1))):
                findings.append(Finding("ALTO", RULE_B64_HIDDEN, source, clean.count("\n", 0, m.start()) + 1,
                                        hidden.replace("\n", " ")[:80]))
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
    # Secreto que se lee y se mete en un parámetro de la tool, en la misma línea.
    for s in secrets:
        for p in (f for f in findings if f.rule == RULE_PARAM):
            if p.source == s.source and p.line == s.line and PARAM_ACQUIRE.search(p.context):
                key = (s.source, s.line, "param")
                if key not in seen:
                    seen.add(key)
                    extra.append(Finding("ALTO", "Secreto metido en un parámetro (posible robo)", s.source, s.line,
                                         f"{s.snippet} → {p.snippet}"[:80]))
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
