"""Arma el holdout v3 (tests/corpus_holdout_v3/) desde fuentes públicas con licencia que permite redistribuir.

Uso: python scripts/importar_holdout_v3.py
- Maliciosos: inyecciones "obvias" de aisa-group/skill-inject (MIT). Cada ataque trae dos redacciones
  (`description_injection` y `line_injection`); cada una va como un SKILL.md. Se excluyen las 8 que el
  paper reclasificó como contextuales (doble uso) y los 48 casos contextuales.
- Benignos: SKILL.md limpios de skill-inject (se saltan los que tienen un LICENSE "All rights reserved")
  y las descripciones de tools de modelcontextprotocol/servers (MIT / Apache 2.0), como `description` MCP.
Los textos se copian tal cual, sin modificarlos. Solo imprime conteos, nunca el contenido.
Revisiones fijadas abajo; sin dependencias (urllib).
"""
from __future__ import annotations

import ast
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "corpus_holdout_v3"

SKILL_INJECT = "aisa-group/skill-inject"
SKILL_INJECT_REV = "b07cfdb2299b07ceb156c227b4b845359bbac363"
MCP_SERVERS = "modelcontextprotocol/servers"
MCP_SERVERS_REV = "36380287ed3b15d115b55f546617d723072b1296"

OBVIOUS = ["data/obvious_injections.json", "data/obvious_injections_camready_phish_poison.json"]
RELABELED = "data/obvious_to_contextual_camready.json"
TS_FILES = ["src/filesystem/server.ts", "src/memory/index.ts", "src/sequentialthinking/index.ts"]
TS_DIRS = ["src/everything/tools/"]
PY_FILES = ["src/fetch/src/mcp_server_fetch/server.py", "src/git/src/mcp_server_git/server.py",
            "src/time/src/mcp_server_time/server.py"]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "agentguard-holdout-import"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def raw(repo: str, rev: str, path: str) -> str:
    return get(f"https://raw.githubusercontent.com/{repo}/{rev}/{path}").decode("utf-8")


def tree(repo: str, rev: str) -> list[str]:
    data = json.loads(get(f"https://api.github.com/repos/{repo}/git/trees/{rev}?recursive=1"))
    if data.get("truncated"):
        raise SystemExit(f"árbol truncado en {repo}")
    return [t["path"] for t in data["tree"] if t["type"] == "blob"]


# --- maliciosos -----------------------------------------------------------------------------------

def malicious_texts() -> list[tuple[str, str]]:
    relabeled = {c["id"] for c in json.loads(raw(SKILL_INJECT, SKILL_INJECT_REV, RELABELED))}
    out, ids = [], set()
    for path in OBVIOUS:
        for c in json.loads(raw(SKILL_INJECT, SKILL_INJECT_REV, path)):
            if c["id"] in relabeled:
                continue
            ids.add(c["id"])
            for field in ("description_injection", "line_injection"):
                text = c["instructions"].get(field) or ""
                if text.strip():
                    out.append((f"{path}#id={c['id']}:{field}", text))
    print(f"Ataques obvios: {len(ids)} (excluidos por reclasificación: {len(relabeled)})")
    return out


# --- benignos: skills ------------------------------------------------------------------------------

def benign_skills(paths: list[str]) -> list[tuple[str, str]]:
    skills = [p for p in paths if p.startswith("data/skills/") and p.endswith("/SKILL.md")]
    licenses = [p for p in paths if p.startswith("data/skills/") and p.rsplit("/", 1)[-1].upper().startswith("LICENSE")]
    restricted = []
    for lic in licenses:
        if "all rights reserved" in raw(SKILL_INJECT, SKILL_INJECT_REV, lic).lower():
            restricted.append(lic.rsplit("/", 1)[0] + "/")
    out = []
    for p in skills:
        if any(p.startswith(r) for r in restricted):
            continue
        out.append((p, raw(SKILL_INJECT, SKILL_INJECT_REV, p)))
    print(f"SKILL.md: {len(skills)}, sin licencia restrictiva: {len(out)} (carpetas restringidas: {len(restricted)})")
    return out


# --- benignos: tools MCP ---------------------------------------------------------------------------

TS_STRING = r'"(?:[^"\\]|\\.)*"'
# Config de una tool: title: "...", description: "..." (+ "..." …). Las descripciones de parámetros usan .describe().
TS_TOOL_DESC = re.compile(r'\btitle:\s*' + TS_STRING + r',\s*description:\s*((?:' + TS_STRING + r'\s*\+?\s*)+)')


def ts_descriptions(source: str) -> list[str]:
    return ["".join(json.loads(s) for s in re.findall(TS_STRING, m.group(1))) for m in TS_TOOL_DESC.finditer(source)]


def py_descriptions(source: str) -> list[str]:
    """`description=` de los decoradores `@<algo>.tool(...)`; resuelve constantes de módulo literales."""
    mod = ast.parse(source)
    consts = {}
    for node in mod.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                continue
            if isinstance(value, str):
                consts[node.targets[0].id] = value
    out = []
    for node in ast.walk(mod):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "tool":
                for kw in dec.keywords:
                    if kw.arg != "description":
                        continue
                    if isinstance(kw.value, ast.Name) and kw.value.id in consts:
                        out.append(consts[kw.value.id])
                        continue
                    try:
                        value = ast.literal_eval(kw.value)
                    except ValueError:
                        continue  # f-string u otra expresión: no se reconstruye
                    if isinstance(value, str):
                        out.append(value)
    return out


def benign_tools(paths: list[str]) -> list[tuple[str, str]]:
    files = TS_FILES + [p for p in paths for d in TS_DIRS if p.startswith(d) and p.endswith(".ts")
                        and not p.endswith("index.ts")]
    out = []
    for p in files:
        out += [(p, d) for d in ts_descriptions(raw(MCP_SERVERS, MCP_SERVERS_REV, p))]
    for p in PY_FILES:
        out += [(p, d) for d in py_descriptions(raw(MCP_SERVERS, MCP_SERVERS_REV, p))]
    print(f"Descripciones de tools MCP: {len(out)}")
    return out


# --- escritura -------------------------------------------------------------------------------------

def write(kind: str, prefix: str, n: int, tipo: str, fmt: str, text: str, fuente: str) -> None:
    data = {"id": f"{prefix}-{n:03d}", "tipo": tipo, "formato": fmt, "texto": text,
            "resultado_esperado": "alerta" if kind == "malicious" else "limpio", "fuente": fuente}
    (OUT / kind / f"{data['id']}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")


def main() -> int:
    if OUT.exists():
        print(f"{OUT} ya existe; no se sobrescribe.")
        return 1
    mal = malicious_texts()
    si_paths = tree(SKILL_INJECT, SKILL_INJECT_REV)
    mcp_paths = tree(MCP_SERVERS, MCP_SERVERS_REV)
    skills = benign_skills(si_paths)
    tools = benign_tools(mcp_paths)
    for kind in ("benign", "malicious"):
        (OUT / kind).mkdir(parents=True)
    si = f"{SKILL_INJECT}@{SKILL_INJECT_REV[:7]}"
    ms = f"{MCP_SERVERS}@{MCP_SERVERS_REV[:7]}"
    for i, (src, text) in enumerate(mal, 1):
        write("malicious", "v3-mal", i, "skill_injection", "skill", text, f"{si}:{src}")
    n = 0
    for src, text in skills:
        n += 1
        write("benign", "v3-benign", n, "skill_real", "skill", text, f"{si}:{src}")
    for src, text in tools:
        n += 1
        write("benign", "v3-benign", n, "tool_mcp_real", "mcp", text, f"{ms}:{src}")
    (OUT / "README.md").write_text(
        "# Holdout v3: skill-inject + modelcontextprotocol/servers\n\n"
        "Convertido con `python scripts/importar_holdout_v3.py`. Los textos se copiaron tal cual.\n\n"
        "| parte | fuente | licencia | commit |\n|---|---|---|---|\n"
        f"| maliciosos ({len(mal)}) | https://github.com/{SKILL_INJECT} (paper: https://arxiv.org/abs/2602.20156) "
        f"| MIT | `{SKILL_INJECT_REV}` |\n"
        f"| benignos: SKILL.md ({len(skills)}) | https://github.com/{SKILL_INJECT} `data/skills/` "
        f"| MIT; algunas skills Apache 2.0 (su LICENSE.txt). Se excluyen las \"All rights reserved\" | `{SKILL_INJECT_REV}` |\n"
        f"| benignos: tools MCP ({len(tools)}) | https://github.com/{MCP_SERVERS} | MIT / Apache 2.0 "
        f"| `{MCP_SERVERS_REV}` |\n\n"
        "Maliciosos: las inyecciones \"obvias\" del benchmark, cada una en sus dos redacciones "
        "(`description_injection` y `line_injection`), cada una sola como SKILL.md. Se excluyen las 8 que el paper "
        "reclasificó como contextuales y los casos contextuales (doble uso). En el paper la inyección va dentro de una "
        "skill más larga; acá va sola, así que es más fácil de ver que en el original.\n\n"
        "Benignos: SKILL.md limpios del mismo benchmark (formato `skill`) y las descripciones de tools de los servidores "
        "de referencia de MCP (formato `mcp`): todo `description` que sigue a un `title` en TypeScript (incluye "
        "algunos campos de esquema, p. ej. del formulario de elicitation del servidor `everything`) y el `description` "
        "de los decoradores `@*.tool` en Python. Las descripciones armadas con f-strings no se incluyen.\n\n"
        "Holdout ciego: no se usa para ajustar reglas. Se mide una sola vez.\n",
        encoding="utf-8")
    print(f"Benignos {n} (skills {len(skills)}, tools {len(tools)}), maliciosos {len(mal)} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
