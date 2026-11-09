"""Mide el scanner actual contra tests/corpus y escribe reports/fase0.md.

Uso: python scripts/medir_corpus.py [--corpus tests/corpus] [--out reports/fase0.md] [--title "..."]
Cada caso se escribe en una carpeta temporal tal como lo vería el scanner
(tool MCP en JSON o SKILL.md) y se revisa con scan_file + escalate, igual que `scan`.
Alerta = al menos un hallazgo ALTO (lo que hace fallar el CI).
En rug_pull se hace lock con texto_antes y verify con texto.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agentguard import cmd_lock, cmd_verify, collect, escalate, scan_file  # noqa: E402

CORPUS = ROOT / "tests" / "corpus"


def write_case(folder: Path, fmt: str, text: str) -> None:
    if fmt == "mcp":
        data = {"tools": [{"name": "tool", "description": text}]}
        (folder / "tools.json").write_text(json.dumps(data), encoding="utf-8")
    else:
        (folder / "SKILL.md").write_text(text, encoding="utf-8")


def scan_case(fmt: str, text: str) -> list:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        write_case(folder, fmt, text)
        return escalate([f for p in collect(folder) for f in scan_file(p)])


def verify_case(before: str, after: str) -> bool:
    """True si verify avisa del cambio (código 1)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        write_case(folder, "mcp", before)
        with redirect_stdout(io.StringIO()):
            cmd_lock(folder)
            write_case(folder, "mcp", after)
            return cmd_verify(folder) == 1


def evaluate(case: dict) -> dict:
    findings = scan_case(case.get("formato", "mcp"), case["texto"])
    altos = [f for f in findings if f.level == "ALTO"]
    medios = [f for f in findings if f.level == "MEDIO"]
    result = {"case": case, "altos": altos, "medios": medios, "scan_alerta": bool(altos)}
    if case["tipo"] == "rug_pull":
        result["verify_alerta"] = verify_case(case["texto_antes"], case["texto"])
        result["alerta"] = result["verify_alerta"]
    else:
        result["alerta"] = result["scan_alerta"]
    result["ok"] = result["alerta"] == (case["resultado_esperado"] == "alerta")
    return result


def load(kind: str, corpus: Path = CORPUS) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((corpus / kind).glob("*.json"))]


def short(text: str, n: int = 110) -> str:
    """Una línea, con los caracteres invisibles o no ASCII visibles como \\uXXXX."""
    s = text.replace("\n", " ").replace("|", "\\|")
    s = s.encode("ascii", "backslashreplace").decode("ascii")
    return s if len(s) <= n else s[:n] + "…"


def rules(findings: list) -> str:
    return ", ".join(sorted({f"{f.level}: {f.rule}" for f in findings})) or "—"


def report(benign: list[dict], malicious: list[dict], title: str = "Fase 0: medición del scanner actual contra el corpus",
           corpus: str = "tests/corpus") -> str:
    tp = sum(r["alerta"] for r in malicious)
    fn = len(malicious) - tp
    fp = sum(r["alerta"] for r in benign)
    tn = len(benign) - fp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / len(malicious) if malicious else 0.0
    lines = [
        f"# {title}",
        "",
        f"Generado por `python scripts/medir_corpus.py` sobre `{corpus}`.",
        "Alerta = al menos un hallazgo ALTO. En `rug_pull`: `lock` con la versión original y `verify` con la nueva.",
        "",
        "## Resumen",
        "",
        "| métrica | valor |",
        "|---|---|",
        f"| casos benignos | {len(benign)} |",
        f"| casos maliciosos | {len(malicious)} |",
        f"| detecciones (verdaderos positivos) | {tp} / {len(malicious)} |",
        f"| falsos negativos (ataques no detectados) | {fn} |",
        f"| falsos positivos (benignos con ALTO) | {fp} / {len(benign)} |",
        f"| benignos limpios | {tn} |",
        f"| tasa de detección (recall) | {recall:.0%} |",
        f"| precisión | {precision:.0%} |",
        "",
        "## Por tipo de ataque",
        "",
        "| tipo | casos | detectados | no detectados |",
        "|---|---|---|---|",
    ]
    total, hit = Counter(), Counter()
    for r in malicious:
        total[r["case"]["tipo"]] += 1
        hit[r["case"]["tipo"]] += r["alerta"]
    for tipo in sorted(total):
        lines.append(f"| {tipo} | {total[tipo]} | {hit[tipo]} | {total[tipo] - hit[tipo]} |")

    rug = [r for r in malicious if r["case"]["tipo"] == "rug_pull"]
    if rug:
        scan_hits = sum(r["scan_alerta"] for r in rug)
        lines += ["", f"Rug pull: `verify` avisa en {sum(r['verify_alerta'] for r in rug)}/{len(rug)} "
                  f"(avisa de cualquier cambio, no juzga si es malo). `scan` del texto nuevo solo da ALTO en "
                  f"{scan_hits}/{len(rug)}: si el usuario aprueba el cambio sin leerlo, el resto pasa."]

    # Solo ids: los textos de ataque nunca se imprimen en un reporte (así un holdout sigue sin leerse).
    lines += ["", "## Falsos negativos (ataques que no dieron ALTO)", ""]
    misses = [r for r in malicious if not r["alerta"]]
    if misses:
        lines += ["| id | tipo | lo que sí vio |", "|---|---|---|"]
        lines += [f"| {r['case']['id']} | {r['case']['tipo']} | {rules(r['medios'])} |" for r in misses]
    else:
        lines.append("Ninguno.")

    lines += ["", "## Falsos positivos (benignos que dieron ALTO)", ""]
    fps = [r for r in benign if r["alerta"]]
    if fps:
        lines += ["| id | texto | reglas ALTO |", "|---|---|---|"]
        lines += [f"| {r['case']['id']} | {short(r['case']['texto'])} | {rules(r['altos'])} |" for r in fps]
    else:
        lines.append("Ninguno.")

    noisy = [r for r in benign if not r["alerta"] and r["medios"]]
    lines += ["", f"## Benignos con avisos MEDIO (no fallan el CI, pero hacen ruido): {len(noisy)}", ""]
    if noisy:
        lines += ["| id | reglas |", "|---|---|"]
        lines += [f"| {r['case']['id']} | {rules(r['medios'])} |" for r in noisy]

    lines += ["", "## Detectados", "", "| id | tipo | reglas ALTO |", "|---|---|---|"]
    lines += [f"| {r['case']['id']} | {r['case']['tipo']} | "
              f"{rules(r['altos']) if r['altos'] else 'verify: cambió'} |" for r in malicious if r["alerta"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    out = ROOT / "reports" / "fase0.md"
    corpus, title = CORPUS, "Fase 0: medición del scanner actual contra el corpus"
    if "--out" in argv:
        out = Path(argv[argv.index("--out") + 1])
    if "--corpus" in argv:
        corpus = Path(argv[argv.index("--corpus") + 1]).resolve()
    if "--title" in argv:
        title = argv[argv.index("--title") + 1]
    benign = [evaluate(c) for c in load("benign", corpus)]
    malicious = [evaluate(c) for c in load("malicious", corpus)]
    label = corpus.relative_to(ROOT).as_posix() if corpus.is_relative_to(ROOT) else str(corpus)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report(benign, malicious, title, label), encoding="utf-8")
    tp = sum(r["alerta"] for r in malicious)
    fp = sum(r["alerta"] for r in benign)
    print(f"Detectados {tp}/{len(malicious)}, falsos positivos {fp}/{len(benign)} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
