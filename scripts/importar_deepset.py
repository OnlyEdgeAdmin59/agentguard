"""Baja deepset/prompt-injections (Apache 2.0) y lo convierte en el holdout v2: tests/corpus_holdout_v2/.

Uso: python scripts/importar_deepset.py
Se baja en JSON desde el datasets-server de Hugging Face (sin dependencias), en la revisión fijada abajo.
Cada texto va como `description` de una tool MCP (formato `mcp`): label 1 → alerta, label 0 → limpio.
Solo imprime conteos, nunca el contenido de los casos (el holdout tiene que seguir ciego).
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "corpus_holdout_v2"
DATASET = "deepset/prompt-injections"
REVISION = "4f61ecb038e9c3fb77e21034b22511b523772cdd"
ROWS = "https://datasets-server.huggingface.co/rows"
PAGE = 100


def fetch_split(split: str) -> list[dict]:
    rows, offset = [], 0
    while True:
        query = urllib.parse.urlencode({"dataset": DATASET, "config": "default", "split": split,
                                        "offset": offset, "length": PAGE})
        with urllib.request.urlopen(f"{ROWS}?{query}", timeout=30) as resp:
            data = json.load(resp)
        rows += [r["row"] for r in data["rows"]]
        offset += PAGE
        if offset >= data["num_rows_total"]:
            return rows


def case(n: int, split: str, row: dict) -> tuple[str, dict]:
    malicious = row["label"] == 1
    kind = "malicious" if malicious else "benign"
    prefix = "dp-mal" if malicious else "dp-benign"
    return kind, {
        "id": f"{prefix}-{n:03d}",
        "tipo": "prompt_injection" if malicious else "texto_normal",
        "formato": "mcp",
        "texto": row["text"],
        "resultado_esperado": "alerta" if malicious else "limpio",
        "fuente": f"{DATASET}@{REVISION[:7]} ({split})",
    }


def main() -> int:
    if OUT.exists():
        print(f"{OUT} ya existe; no se sobrescribe.")
        return 1
    counts = {"benign": 0, "malicious": 0}
    for kind in counts:
        (OUT / kind).mkdir(parents=True)
    for split in ("train", "test"):
        for row in fetch_split(split):
            kind, data = case(counts["benign"] + counts["malicious"] + 1, split, row)
            counts[kind] += 1
            path = OUT / kind / f"{data['id']}.json"
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Holdout v2: deepset/prompt-injections\n\n"
        f"Fuente: https://huggingface.co/datasets/{DATASET} (revisión `{REVISION}`), licencia Apache 2.0, "
        "autor deepset GmbH. Convertido con `python scripts/importar_deepset.py`; los textos no se modificaron.\n\n"
        "Holdout ciego: no se usa para ajustar reglas. Cada texto va como `description` de una tool MCP.\n"
        "Ojo: es prompt injection en general (parte en alemán), no descripciones de herramientas reales.\n",
        encoding="utf-8")
    print(f"Benignos {counts['benign']}, maliciosos {counts['malicious']} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
