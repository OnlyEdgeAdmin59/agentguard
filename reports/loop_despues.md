# Fase 0: medición del scanner actual contra el corpus

Generado por `python scripts/medir_corpus.py` sobre `tests/corpus`.
Alerta = al menos un hallazgo ALTO. En `rug_pull`: `lock` con la versión original y `verify` con la nueva.

## Resumen

| métrica | valor |
|---|---|
| casos benignos | 34 |
| casos maliciosos | 33 |
| detecciones (verdaderos positivos) | 33 / 33 |
| falsos negativos (ataques no detectados) | 0 |
| falsos positivos (benignos con ALTO) | 0 / 34 |
| benignos limpios | 34 |
| tasa de detección (recall) | 100% |
| precisión | 100% |

## Por tipo de ataque

| tipo | casos | detectados | no detectados |
|---|---|---|---|
| exfiltracion | 9 | 9 | 0 |
| instrucciones_ocultas | 9 | 9 | 0 |
| rug_pull | 4 | 4 | 0 |
| tool_shadowing | 5 | 5 | 0 |
| unicode_invisible | 6 | 6 | 0 |

Rug pull: `verify` avisa en 4/4 (avisa de cualquier cambio, no juzga si es malo). `scan` del texto nuevo solo da ALTO en 2/4: si el usuario aprueba el cambio sin leerlo, el resto pasa.

## Falsos negativos (ataques que no dieron ALTO)

Ninguno.

## Falsos positivos (benignos que dieron ALTO)

Ninguno.

## Benignos con avisos MEDIO (no fallan el CI, pero hacen ruido): 9

| id | reglas |
|---|---|
| benign-020 | MEDIO: Menciona secretos |
| benign-021 | MEDIO: Anula instrucciones previas |
| benign-022 | MEDIO: Envío de datos a URL externa, MEDIO: Menciona secretos |
| benign-025 | MEDIO: Pide ocultar algo al usuario |
| benign-026 | MEDIO: Envío de datos a URL externa, MEDIO: Menciona secretos |
| benign-027 | MEDIO: Envío de datos a URL externa |
| benign-029 | MEDIO: Menciona secretos |
| benign-032 | MEDIO: Anula instrucciones previas, MEDIO: Etiquetas de urgencia para el modelo |
| benign-033 | MEDIO: Menciona secretos |

## Detectados

| id | tipo | reglas ALTO |
|---|---|---|
| mal-001 | instrucciones_ocultas | ALTO: Pide ocultar algo al usuario |
| mal-002 | instrucciones_ocultas | ALTO: Anula instrucciones previas |
| mal-003 | instrucciones_ocultas | ALTO: Instrucción oculta en comentario HTML |
| mal-004 | instrucciones_ocultas | ALTO: Anula instrucciones previas |
| mal-005 | instrucciones_ocultas | ALTO: Anula instrucciones previas |
| mal-006 | instrucciones_ocultas | ALTO: Instrucción oculta en comentario HTML |
| mal-007 | instrucciones_ocultas | ALTO: Anula instrucciones previas, ALTO: Pide ocultar algo al usuario |
| mal-008 | instrucciones_ocultas | ALTO: Anula instrucciones previas, ALTO: Pide hacer algo a escondidas |
| mal-009 | exfiltracion | ALTO: Secreto + envío externo (posible robo) |
| mal-010 | exfiltracion | ALTO: Secreto + envío externo (posible robo) |
| mal-011 | exfiltracion | ALTO: Secreto + envío externo (posible robo) |
| mal-012 | exfiltracion | ALTO: Secreto + envío externo (posible robo) |
| mal-013 | exfiltracion | ALTO: Secreto metido en un parámetro (posible robo) |
| mal-014 | exfiltracion | ALTO: Secreto metido en un parámetro (posible robo) |
| mal-015 | exfiltracion | ALTO: Secreto + envío externo (posible robo) |
| mal-016 | exfiltracion | ALTO: Secreto + envío externo (posible robo) |
| mal-017 | exfiltracion | ALTO: Imagen markdown que filtra datos por la URL |
| mal-018 | tool_shadowing | ALTO: Cambia cómo se usan otras herramientas (tool shadowing) |
| mal-019 | tool_shadowing | ALTO: Cambia cómo se usan otras herramientas (tool shadowing) |
| mal-020 | tool_shadowing | ALTO: Cambia cómo se usan otras herramientas (tool shadowing) |
| mal-021 | tool_shadowing | ALTO: Cambia cómo se usan otras herramientas (tool shadowing) |
| mal-022 | tool_shadowing | ALTO: Cambia cómo se usan otras herramientas (tool shadowing) |
| mal-023 | unicode_invisible | ALTO: Caracteres invisibles (texto escondido) |
| mal-024 | unicode_invisible | ALTO: Caracteres invisibles (texto escondido) |
| mal-025 | unicode_invisible | ALTO: Caracteres invisibles (texto escondido) |
| mal-026 | unicode_invisible | ALTO: Anula instrucciones previas, ALTO: Caracteres invisibles (texto escondido) |
| mal-027 | unicode_invisible | ALTO: Anula instrucciones previas, ALTO: Letras de otro alfabeto que imitan latinas (homoglifos) |
| mal-028 | unicode_invisible | ALTO: Caracteres invisibles (texto escondido) |
| mal-029 | instrucciones_ocultas | ALTO: Instrucción escondida en base64 |
| mal-030 | rug_pull | verify: cambió |
| mal-031 | rug_pull | ALTO: Pide hacer algo a escondidas |
| mal-032 | rug_pull | verify: cambió |
| mal-033 | rug_pull | ALTO: Caracteres invisibles (texto escondido) |
