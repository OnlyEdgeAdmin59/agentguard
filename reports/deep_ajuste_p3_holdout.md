# prompt v3 haiku holdout

Generado por `python scripts/medir_deep.py` sobre `tests/corpus_holdout` con anthropic `claude-haiku-5-5` (prompt v3, esfuerzo low). Alerta = hallazgo ALTO. Aviso = ALTO o MEDIO.

## Corrida 1

| | solo reglas | solo deep | combinado |
|---|---|---|---|
| ataques con ALTO (por texto) | 22/23 (96%) | 23/23 (100%) | 23/23 (100%) |
| ataques con algún aviso (por texto) | 22/23 (96%) | 23/23 (100%) | 23/23 (100%) |
| benignos con ALTO (falsas alarmas) | 1/23 (4%) | 0/23 (0%) | 1/23 (4%) |
| benignos con algún aviso | 3/23 (13%) | 2/23 (9%) | 4/23 (17%) |

Sin veredicto: 0. Casos juzgados: 46 de 46.

## Corrida 2

| | solo reglas | solo deep | combinado |
|---|---|---|---|
| ataques con ALTO (por texto) | 22/23 (96%) | 23/23 (100%) | 23/23 (100%) |
| ataques con algún aviso (por texto) | 22/23 (96%) | 23/23 (100%) | 23/23 (100%) |
| benignos con ALTO (falsas alarmas) | 1/23 (4%) | 0/23 (0%) | 1/23 (4%) |
| benignos con algún aviso | 3/23 (13%) | 0/23 (0%) | 3/23 (13%) |

Sin veredicto: 0. Casos juzgados: 46 de 46.

## Corrida 3

| | solo reglas | solo deep | combinado |
|---|---|---|---|
| ataques con ALTO (por texto) | 22/23 (96%) | 23/23 (100%) | 23/23 (100%) |
| ataques con algún aviso (por texto) | 22/23 (96%) | 23/23 (100%) | 23/23 (100%) |
| benignos con ALTO (falsas alarmas) | 1/23 (4%) | 0/23 (0%) | 1/23 (4%) |
| benignos con algún aviso | 3/23 (13%) | 2/23 (9%) | 4/23 (17%) |

Sin veredicto: 0. Casos juzgados: 46 de 46.

## Costo

138 llamadas, tokens 177291 entrada / 20267 salida, costo $0.03.

## Benignos con ALTO de deep (falsas alarmas)

Ninguno.

## Ataques sin ALTO (ni reglas ni deep)

Ninguno.

## Ataques que solo vieron las reglas (deep sin ALTO)

Ninguno.
