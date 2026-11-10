"""Mide `scan --deep` contra un corpus y lleva la cuenta de lo gastado en la API.

Uso:
  python scripts/medir_deep.py --corpus tests/corpus --out reports/deep_ajuste.md --yes
      [--model claude-haiku-5-5] [--provider anthropic|ollama] [--repeticiones 1] [--hilos 8]
      [--presupuesto 15] [--detalle] [--dry-run]

- Compara solo reglas, solo deep y la combinación (ALTO de cualquiera de los dos).
- Si los casos traen `#id=` en la fuente (Skill-Inject), también cuenta por ataque distinto.
- El reporte nunca imprime textos de ataque. `--detalle` agrega el motivo del juez para cada caso, y
  está prohibido en el holdout v3 (ciego).
- Costos: cada corrida con Anthropic suma una fila a reports/deep_costos.md. Antes de enviar se estima el
  costo; si lo gastado + lo estimado pasa el 90% del presupuesto, no corre. Durante la corrida, si lo
  gastado pasa el 95%, se detiene y guarda lo que tenga.
- El holdout v3 se mide una sola vez: hace falta `--ciego-final` y se niega si el reporte ya existe.
"""
from __future__ import annotations

import io
import json
import re
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from agentguard import deep  # noqa: E402
from medir_corpus import evaluate, load  # noqa: E402

LEDGER = ROOT / "reports" / "deep_costos.md"
BLIND = (ROOT / "tests" / "corpus_holdout_v3").resolve()
ATTACK_ID = re.compile(r"(data/[^#]+)#id=([^:]+):")


def arg(argv: list[str], name: str, default: str | None = None) -> str | None:
    return argv[argv.index(name) + 1] if name in argv else default


def spent() -> float:
    if not LEDGER.exists():
        return 0.0
    total = 0.0
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*\d{4}-\d\d-\d\d.*\|\s*\$([\d.]+)\s*\|\s*$", line)
        if m:
            total += float(m.group(1))
    return total


def log_cost(corpus: str, model: str, calls: int, tin: int, tout: int, cost: float, note: str) -> None:
    if not LEDGER.exists():
        LEDGER.write_text("# Costos de `--deep` (API de Anthropic)\n\nTope total: $15. Fuente: `usage` de cada "
                          "respuesta y la tabla de precios de `agentguard/deep.py`.\n\n"
                          "| fecha | corpus | modelo | prompt | nota | llamadas | tokens entrada | tokens salida "
                          "| costo |\n|---|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(f"| {datetime.now():%Y-%m-%d %H:%M} | {corpus} | {model} | {deep.PROMPT_VERSION} | {note} | {calls} "
                f"| {tin} | {tout} | ${cost:.4f} |\n")


def unit_for(case: dict) -> deep.Unit:
    if case.get("formato", "mcp") == "mcp":
        text = json.dumps({"name": "tool", "description": case["texto"]}, ensure_ascii=False, indent=1)
        return deep.Unit(case["id"], text, "tool")
    return deep.Unit(case["id"], case["texto"], "skill")


class Budget:
    def __init__(self, limit: float, model: str):
        self.limit, self.model = limit, model
        self.base = spent()
        self.stats = deep.Stats(model=model)
        self.lock = threading.Lock()
        self.stopped = False

    def add(self, s: deep.Stats) -> None:
        with self.lock:
            self.stats.calls += s.calls
            self.stats.input_tokens += s.input_tokens
            self.stats.output_tokens += s.output_tokens
            self.stats.no_verdict += s.no_verdict
            cost = self.stats.cost() or 0.0
            if self.base + cost > 0.95 * self.limit:
                self.stopped = True


def judge_cases(cases: list[dict], transport, model: str, budget: Budget, threads: int) -> dict[str, list]:
    out: dict[str, list] = {}

    def one(case):
        if budget.stopped:
            return
        s = deep.Stats(model=model)
        out[case["id"]] = deep.judge_unit(unit_for(case), transport, "es", s)
        budget.add(s)

    with ThreadPoolExecutor(max_workers=threads) as pool:
        list(pool.map(one, cases))
    return out


def levels(findings: list) -> set[str]:
    return {f.level for f in findings}


def summarize(cases: list[dict], rules: dict, verdicts: dict) -> dict:
    n = len(cases)
    r_alto = sum(rules[c["id"]]["alerta"] for c in cases)
    r_aviso = sum(rules[c["id"]]["alerta"] or bool(rules[c["id"]]["medios"]) for c in cases)
    d_alto = sum("ALTO" in levels(verdicts.get(c["id"], [])) for c in cases)
    d_aviso = sum(bool(levels(verdicts.get(c["id"], [])) & {"ALTO", "MEDIO"}) for c in cases)
    c_alto = sum(rules[c["id"]]["alerta"] or "ALTO" in levels(verdicts.get(c["id"], [])) for c in cases)
    c_aviso = sum(rules[c["id"]]["alerta"] or bool(rules[c["id"]]["medios"])
                  or bool(levels(verdicts.get(c["id"], [])) & {"ALTO", "MEDIO"}) for c in cases)
    none = sum(any(f.rule == deep.RULE_DEEP_NONE for f in verdicts.get(c["id"], [])) for c in cases)
    return dict(n=n, r_alto=r_alto, r_aviso=r_aviso, d_alto=d_alto, d_aviso=d_aviso, c_alto=c_alto,
                c_aviso=c_aviso, none=none, judged=sum(c["id"] in verdicts for c in cases))


def by_attack(cases: list[dict], rules: dict, verdicts: dict) -> dict | None:
    groups = defaultdict(list)
    for c in cases:
        m = ATTACK_ID.search(c.get("fuente", ""))
        if not m:
            return None
        groups[m.groups()].append(c["id"])
    rank = lambda cid: (2 if rules[cid]["alerta"] or "ALTO" in levels(verdicts.get(cid, [])) else  # noqa: E731
                        1 if rules[cid]["medios"] or levels(verdicts.get(cid, [])) & {"MEDIO"} else 0)
    rank_r = lambda cid: 2 if rules[cid]["alerta"] else 1 if rules[cid]["medios"] else 0  # noqa: E731
    rank_d = lambda cid: (2 if "ALTO" in levels(verdicts.get(cid, [])) else  # noqa: E731
                          1 if "MEDIO" in levels(verdicts.get(cid, [])) else 0)
    out = {}
    for name, fn in (("reglas", rank_r), ("deep", rank_d), ("combinado", rank)):
        best = [max(fn(cid) for cid in ids) for ids in groups.values()]
        out[name] = (sum(b == 2 for b in best), sum(b >= 1 for b in best), len(best))
    return out


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({a / b:.0%})" if b else "0/0"


def render(title: str, corpus: str, model: str, provider: str, reps: list[dict], stats: deep.Stats,
           detail: bool, mal: list[dict], ben: list[dict], last_rules: dict, last_verdicts: dict) -> str:
    lines = [f"# {title}", "",
             f"Generado por `python scripts/medir_deep.py` sobre `{corpus}` con {provider} `{model}` "
             f"(prompt {deep.PROMPT_VERSION}, esfuerzo low). Alerta = hallazgo ALTO. Aviso = ALTO o MEDIO.", ""]
    for i, rep in enumerate(reps, 1):
        m, b = rep["mal"], rep["ben"]
        head = f"## Corrida {i}" if len(reps) > 1 else "## Resultado"
        lines += [head, "", "| | solo reglas | solo deep | combinado |", "|---|---|---|---|",
                  f"| ataques con ALTO (por texto) | {pct(m['r_alto'], m['n'])} | {pct(m['d_alto'], m['n'])} "
                  f"| {pct(m['c_alto'], m['n'])} |",
                  f"| ataques con algún aviso (por texto) | {pct(m['r_aviso'], m['n'])} | {pct(m['d_aviso'], m['n'])} "
                  f"| {pct(m['c_aviso'], m['n'])} |",
                  f"| benignos con ALTO (falsas alarmas) | {pct(b['r_alto'], b['n'])} | {pct(b['d_alto'], b['n'])} "
                  f"| {pct(b['c_alto'], b['n'])} |",
                  f"| benignos con algún aviso | {pct(b['r_aviso'], b['n'])} | {pct(b['d_aviso'], b['n'])} "
                  f"| {pct(b['c_aviso'], b['n'])} |", ""]
        if rep.get("attack"):
            a = rep["attack"]
            lines += ["Por ataque distinto:", "", "| | solo reglas | solo deep | combinado |", "|---|---|---|---|",
                      "| ataques con ALTO | " + " | ".join(pct(a[k][0], a[k][2]) for k in ("reglas", "deep", "combinado"))
                      + " |",
                      "| ataques con algún aviso | " + " | ".join(pct(a[k][1], a[k][2])
                                                              for k in ("reglas", "deep", "combinado")) + " |", ""]
        lines += [f"Sin veredicto: {m['none'] + b['none']}. Casos juzgados: {m['judged'] + b['judged']} de "
                  f"{m['n'] + b['n']}.", ""]
    cost = stats.cost()
    lines += ["## Costo", "", f"{stats.calls} llamadas, tokens {stats.input_tokens} entrada / {stats.output_tokens} "
              f"salida, costo {deep.money(cost) if cost is not None else '—'}.", ""]
    # solo ids, nunca textos de ataque
    fp = [c for c in ben if "ALTO" in levels(last_verdicts.get(c["id"], []))]
    lines += ["## Benignos con ALTO de deep (falsas alarmas)", ""]
    lines += [f"- {c['id']}" + (f": {last_verdicts[c['id']][0].reason}" if detail else "") for c in fp] or ["Ninguno."]
    miss = [c for c in mal if not (last_rules[c["id"]]["alerta"] or "ALTO" in levels(last_verdicts.get(c["id"], [])))]
    lines += ["", "## Ataques sin ALTO (ni reglas ni deep)", ""]
    for c in miss:
        v = last_verdicts.get(c["id"], [])
        lvl = ",".join(sorted(levels(v))) or "LIMPIO"
        lines.append(f"- {c['id']} ({lvl})" + (f": {v[0].reason}" if detail and v else ""))
    if not miss:
        lines.append("Ninguno.")
    deep_miss = [c for c in mal if c not in miss and "ALTO" not in levels(last_verdicts.get(c["id"], []))]
    lines += ["", "## Ataques que solo vieron las reglas (deep sin ALTO)", ""]
    for c in deep_miss:
        v = last_verdicts.get(c["id"], [])
        lvl = ",".join(sorted(levels(v))) or "LIMPIO"
        lines.append(f"- {c['id']} ({c.get('tipo', '?')}, {lvl})" + (f": {v[0].reason}" if detail and v else ""))
    if not deep_miss:
        lines.append("Ninguno.")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    corpus = Path(arg(argv, "--corpus", "tests/corpus")).resolve()
    blind = corpus == BLIND
    default_out = ROOT / "reports" / ("deep_holdout_v3.md" if blind else "deep_ajuste.md")
    out = Path(arg(argv, "--out", str(default_out)))
    model = arg(argv, "--model", deep.DEFAULT_MODEL)
    provider = arg(argv, "--provider", "anthropic")
    reps_n = int(arg(argv, "--repeticiones", "1"))
    threads = int(arg(argv, "--hilos", "8"))
    limit = float(arg(argv, "--presupuesto", "15"))
    title = arg(argv, "--title", f"Medición de --deep: {corpus.name}")
    detail = "--detalle" in argv
    if blind:
        if detail:
            print("--detalle está prohibido en el holdout v3 (ciego).")
            return 2
        if "--ciego-final" not in argv:
            print("El holdout v3 se mide una sola vez: agrega --ciego-final.")
            return 2
        if out.exists():
            print(f"{out} ya existe: el holdout v3 ya se midió.")
            return 2
        if reps_n != 1:
            print("El holdout v3 se mide una sola vez (--repeticiones 1).")
            return 2
    ben, mal = load("benign", corpus), load("malicious", corpus)
    cases = ben + mal
    units = [unit_for(c) for c in cases]
    tokens, est = deep.estimate(units, model)
    est = (est or 0.0) * reps_n
    base = spent()
    label = corpus.relative_to(ROOT).as_posix() if corpus.is_relative_to(ROOT) else str(corpus)
    print(f"{label}: {len(cases)} casos, ~{tokens * reps_n} tokens, costo estimado {deep.money(est)} "
          f"(gastado hasta ahora {deep.money(base)} de ${limit:.0f}).")
    if "--dry-run" in argv:
        return 0
    if provider == "anthropic" and base + est > 0.9 * limit:
        print("No corre: pasaría el 90% del presupuesto.")
        return 2
    if "--yes" not in argv:
        print("Agrega --yes para enviar.")
        return 2
    transport = deep.make_transport(provider, model)
    with redirect_stdout(io.StringIO()):
        rules = {c["id"]: evaluate(c) for c in cases}
    budget = Budget(limit if provider == "anthropic" else float("inf"), model)
    reps, verdicts = [], {}
    for _ in range(reps_n):
        verdicts = judge_cases(cases, transport, model, budget, threads)
        reps.append({"mal": summarize(mal, rules, verdicts), "ben": summarize(ben, rules, verdicts),
                     "attack": by_attack(mal, rules, verdicts)})
        if budget.stopped:
            break
    note = "parcial: tope" if budget.stopped else ("ciego final" if blind else f"{len(reps)} corrida(s)")
    if provider == "anthropic":
        log_cost(label, model, budget.stats.calls, budget.stats.input_tokens, budget.stats.output_tokens,
                 budget.stats.cost() or 0.0, note)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(title, label, model, provider, reps, budget.stats, detail, mal, ben,
                          rules, verdicts), encoding="utf-8")
    last = reps[-1]
    print(f"deep ALTO {last['mal']['d_alto']}/{last['mal']['n']}, combinado {last['mal']['c_alto']}/"
          f"{last['mal']['n']}; FP deep {last['ben']['d_alto']}/{last['ben']['n']}; costo "
          f"{deep.money(budget.stats.cost())}; total gastado {deep.money(spent())} -> {out}")
    if budget.stopped:
        print("DETENIDO: se acercó al tope del presupuesto.")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
