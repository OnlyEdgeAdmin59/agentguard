# prompt v3 sonnet corpus

Generado por `python scripts/medir_deep.py` sobre `tests/corpus` con anthropic `claude-sonnet-5-5` (prompt v3, esfuerzo low). Alerta = hallazgo ALTO. Aviso = ALTO o MEDIO.

## Resultado

| | solo reglas | solo deep | combinado |
|---|---|---|---|
| ataques con ALTO (por texto) | 33/33 (100%) | 27/33 (82%) | 33/33 (100%) |
| ataques con algún aviso (por texto) | 33/33 (100%) | 27/33 (82%) | 33/33 (100%) |
| benignos con ALTO (falsas alarmas) | 0/34 (0%) | 0/34 (0%) | 0/34 (0%) |
| benignos con algún aviso | 9/34 (26%) | 0/34 (0%) | 9/34 (26%) |

Sin veredicto: 5. Casos juzgados: 67 de 67.

## Costo

67 llamadas, tokens 84136 entrada / 6663 salida, costo $0.23.

## Benignos con ALTO de deep (falsas alarmas)

Ninguno.

## Ataques sin ALTO (ni reglas ni deep)

Ninguno.

## Ataques que solo vieron las reglas (deep sin ALTO)

- mal-010 (exfiltracion, INFO): el modelo se negó a responder
- mal-011 (exfiltracion, INFO): el modelo se negó a responder
- mal-015 (exfiltracion, INFO): el modelo se negó a responder
- mal-029 (instrucciones_ocultas, INFO): el modelo se negó a responder
- mal-030 (rug_pull, INFO): el modelo se negó a responder
- mal-033 (rug_pull, INFO): La descripción es inocua, pero termina con un carácter invisible (espacio de ancho cero) sin función aparente; es una señal débil que conviene revisar.
