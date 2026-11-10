"""Falsas alarmas de `--deep` en skills reales: solo archivos SKILL.md bajo ~/.claude/skills y ~/.claude/plugins.

Uso:
  python scripts/ruido_deep.py --dry-run           cuenta archivos y estima costo; no envía nada
  python scripts/ruido_deep.py --yes [--hilos 8]   envía a Anthropic (Haiku, prompt actual) y cuenta

Privacidad:
- Solo SKILL.md. Nunca .json ni otros .md, ni carpetas de credenciales o sesiones (se verifica la ruta).
- Secretos con forma de clave se tapan antes de enviar (deep.redact).
- El archivo de salida guarda solo conteos. Las rutas de los ALTO se imprimen en la terminal para revisarlas a
  mano y no se guardan.
- El costo se suma a reports/deep_costos.md.
"""
from __future__ import annotations

import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from agentguard import collect, deep  # noqa: E402
from medir_deep import log_cost, spent  # noqa: E402

HOME = Path.home() / ".claude"
ALLOWED_TOP = {"skills", "plugins"}
FORBIDDEN_DIRS = {"projects", "sessions", "todos", "shell-snapshots", "statsig", "history", ".credentials",
                  "credentials", "secrets", "ide", "logs", "debug"}


def skill_files() -> list[Path]:
    out = []
    for p in map(Path, collect(HOME)):
        rel = p.relative_to(HOME)
        dirs = {d.lower() for d in rel.parts[:-1]}
        if p.name == "SKILL.md" and rel.parts[0] in ALLOWED_TOP and not dirs & FORBIDDEN_DIRS:
            out.append(p)
    return out


def main(argv: list[str]) -> int:
    model = deep.DEFAULT_MODEL
    files = skill_files()
    units = [u for p in files for u in deep.units_from_file(p)]
    calls = sum(len(deep.chunks(u.text)) for u in units)
    tokens, est = deep.estimate(units, model)
    print(f"{len(files)} SKILL.md, {calls} llamadas, ~{tokens} tokens, costo estimado {deep.money(est)} "
          f"(gastado hasta ahora {deep.money(spent())} de $15).")
    if "--dry-run" in argv:
        return 0
    if spent() + (est or 0) > 0.9 * 15:
        print("No corre: pasaría el 90% del presupuesto.")
        return 2
    if "--yes" not in argv:
        print("Agrega --yes para enviar.")
        return 2
    threads = int(argv[argv.index("--hilos") + 1]) if "--hilos" in argv else 8
    transport = deep.make_transport("anthropic", model)
    stats, lock = deep.Stats(model=model), threading.Lock()
    results: dict[str, set[str]] = {}
    altos: list[tuple[str, str]] = []

    def one(u: deep.Unit) -> None:
        s = deep.Stats(model=model)
        found = deep.judge_unit(u, transport, "es", s)
        with lock:
            for k in ("calls", "input_tokens", "output_tokens", "no_verdict", "redacted"):
                setattr(stats, k, getattr(stats, k) + getattr(s, k))
            results[u.source] = {f.level for f in found if f.rule == deep.RULE_DEEP}
            altos.extend((u.source, f.reason) for f in found if f.level == "ALTO")

    with ThreadPoolExecutor(max_workers=threads) as pool:
        list(pool.map(one, units))
    n = len(results)
    alto = sum("ALTO" in v for v in results.values())
    aviso = sum(bool(v & {"ALTO", "MEDIO"}) for v in results.values())
    info = sum(v == {"INFO"} for v in results.values())
    cost = stats.cost() or 0.0
    log_cost("~/.claude SKILL.md (ruido)", model, stats.calls, stats.input_tokens, stats.output_tokens, cost,
             "skills reales")
    print(f"juzgados {n}; ALTO {alto}; algún aviso {aviso}; solo INFO {info}; sin veredicto {stats.no_verdict}; "
          f"secretos tapados {stats.redacted}; costo {deep.money(cost)}; total {deep.money(spent())}")
    print(Counter(lvl for v in results.values() for lvl in v))
    print("\nALTO (para revisar a mano, no se guarda):")
    for src, reason in sorted(altos):
        print(f"- {Path(src).relative_to(HOME).parent.as_posix()}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
