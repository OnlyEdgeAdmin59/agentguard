# v1 haiku holdout

Generado por `python scripts/medir_deep.py` sobre `tests/corpus_holdout` con anthropic `claude-haiku-5-5` (prompt v1, esfuerzo low). Alerta = hallazgo ALTO. Aviso = ALTO o MEDIO.

## Resultado

| | solo reglas | solo deep | combinado |
|---|---|---|---|
| ataques con ALTO (por texto) | 22/23 (96%) | 23/23 (100%) | 23/23 (100%) |
| ataques con algún aviso (por texto) | 22/23 (96%) | 23/23 (100%) | 23/23 (100%) |
| benignos con ALTO (falsas alarmas) | 1/23 (4%) | 0/23 (0%) | 1/23 (4%) |
| benignos con algún aviso | 3/23 (13%) | 2/23 (9%) | 4/23 (17%) |

Sin veredicto: 0. Casos juzgados: 46 de 46.

## Costo

46 llamadas, tokens 49619 entrada / 6313 salida, costo $0.0081.

## Benignos con ALTO de deep (falsas alarmas)

Ninguno.

## Ataques sin ALTO (ni reglas ni deep)

Ninguno.
