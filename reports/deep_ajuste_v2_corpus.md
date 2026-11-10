# v2 haiku corpus

Generado por `python scripts/medir_deep.py` sobre `tests/corpus` con anthropic `claude-haiku-5-5` (prompt v2, esfuerzo low). Alerta = hallazgo ALTO. Aviso = ALTO o MEDIO.

## Corrida 1

| | solo reglas | solo deep | combinado |
|---|---|---|---|
| ataques con ALTO (por texto) | 33/33 (100%) | 31/33 (94%) | 33/33 (100%) |
| ataques con algún aviso (por texto) | 33/33 (100%) | 32/33 (97%) | 33/33 (100%) |
| benignos con ALTO (falsas alarmas) | 0/34 (0%) | 0/34 (0%) | 0/34 (0%) |
| benignos con algún aviso | 9/34 (26%) | 2/34 (6%) | 9/34 (26%) |

Sin veredicto: 0. Casos juzgados: 67 de 67.

## Corrida 2

| | solo reglas | solo deep | combinado |
|---|---|---|---|
| ataques con ALTO (por texto) | 33/33 (100%) | 31/33 (94%) | 33/33 (100%) |
| ataques con algún aviso (por texto) | 33/33 (100%) | 32/33 (97%) | 33/33 (100%) |
| benignos con ALTO (falsas alarmas) | 0/34 (0%) | 0/34 (0%) | 0/34 (0%) |
| benignos con algún aviso | 9/34 (26%) | 2/34 (6%) | 9/34 (26%) |

Sin veredicto: 0. Casos juzgados: 67 de 67.

## Corrida 3

| | solo reglas | solo deep | combinado |
|---|---|---|---|
| ataques con ALTO (por texto) | 33/33 (100%) | 32/33 (97%) | 33/33 (100%) |
| ataques con algún aviso (por texto) | 33/33 (100%) | 32/33 (97%) | 33/33 (100%) |
| benignos con ALTO (falsas alarmas) | 0/34 (0%) | 0/34 (0%) | 0/34 (0%) |
| benignos con algún aviso | 9/34 (26%) | 2/34 (6%) | 9/34 (26%) |

Sin veredicto: 0. Casos juzgados: 67 de 67.

## Costo

201 llamadas, tokens 247218 entrada / 21064 salida, costo $0.04.

## Benignos con ALTO de deep (falsas alarmas)

Ninguno.

## Ataques sin ALTO (ni reglas ni deep)

Ninguno.

## Ataques que solo vieron las reglas (deep sin ALTO)

- mal-033 (rug_pull, LIMPIO)
