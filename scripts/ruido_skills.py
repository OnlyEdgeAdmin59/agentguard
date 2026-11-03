"""Control de ruido: cuenta hallazgos del scanner sobre skills reales (por defecto ~/.claude) y compara con una base.

Uso:
  python scripts/ruido_skills.py --guardar-base     guarda los conteos actuales en reports/ruido_base.json
  python scripts/ruido_skills.py                    compara contra la base; código 1 si se pasa de los límites
Límites: ALTO no puede pasar de la base (1) y MEDIO no puede subir más de 10%.
Privacidad: solo se guardan y se imprimen números por regla; nunca rutas ni contenido.
"""
from __future__ import annotations

import io
import json
import sys
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agentguard import collect, escalate, scan_file  # noqa: E402

BASE = ROOT / "reports" / "ruido_base.json"
MAX_ALTO = 1
MAX_MEDIO_SUBA = 0.10


def count(target: Path) -> dict:
    files = collect(target)
    with redirect_stdout(io.StringIO()):
        findings = [f for f in escalate([f for p in files for f in scan_file(p)]) if f.level != "PISTA"]
    by_rule = Counter(f"{f.level}: {f.rule}" for f in findings)
    return {"archivos": len(files), "ALTO": sum(f.level == "ALTO" for f in findings),
            "MEDIO": sum(f.level == "MEDIO" for f in findings), "por_regla": dict(sorted(by_rule.items()))}


def main(argv: list[str]) -> int:
    target = Path(argv[argv.index("--dir") + 1]) if "--dir" in argv else Path.home() / ".claude"
    now = count(target)
    if "--guardar-base" in argv:
        BASE.write_text(json.dumps(now, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Base guardada: {now['archivos']} archivos, ALTO {now['ALTO']}, MEDIO {now['MEDIO']}")
        return 0
    base = json.loads(BASE.read_text(encoding="utf-8"))
    limit_medio = int(base["MEDIO"] * (1 + MAX_MEDIO_SUBA))
    ok = now["ALTO"] <= MAX_ALTO and now["MEDIO"] <= limit_medio
    print(f"ALTO {now['ALTO']} (límite {MAX_ALTO}) | MEDIO {now['MEDIO']} (base {base['MEDIO']}, límite {limit_medio})"
          f" | {'OK' if ok else 'SE PASA'}")
    for rule in sorted(set(base["por_regla"]) | set(now["por_regla"])):
        a, b = base["por_regla"].get(rule, 0), now["por_regla"].get(rule, 0)
        if a != b:
            print(f"  {rule}: {a} -> {b}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
