# v1 haiku corpus

Generado por `python scripts/medir_deep.py` sobre `tests/corpus` con anthropic `claude-haiku-5-5` (prompt v1, esfuerzo low). Alerta = hallazgo ALTO. Aviso = ALTO o MEDIO.

## Resultado

| | solo reglas | solo deep | combinado |
|---|---|---|---|
| ataques con ALTO (por texto) | 33/33 (100%) | 30/33 (91%) | 33/33 (100%) |
| ataques con algún aviso (por texto) | 33/33 (100%) | 32/33 (97%) | 33/33 (100%) |
| benignos con ALTO (falsas alarmas) | 0/34 (0%) | 0/34 (0%) | 0/34 (0%) |
| benignos con algún aviso | 9/34 (26%) | 2/34 (6%) | 9/34 (26%) |

Sin veredicto: 0. Casos juzgados: 67 de 67.

## Costo

67 llamadas, tokens 70434 entrada / 7724 salida, costo $0.01.

## Benignos con ALTO de deep (falsas alarmas)

Ninguno.

## Ataques sin ALTO (ni reglas ni deep)

Ninguno.
