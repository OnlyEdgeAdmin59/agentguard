# Fase 0: medición del scanner actual contra el corpus

Generado por `python scripts/medir_corpus.py` sobre `tests/corpus_holdout_v3`.
Alerta = al menos un hallazgo ALTO. En `rug_pull`: `lock` con la versión original y `verify` con la nueva.

## Resumen

| métrica | valor |
|---|---|
| casos benignos | 120 |
| casos maliciosos | 60 |
| detecciones (verdaderos positivos) | 2 / 60 |
| falsos negativos (ataques no detectados) | 58 |
| falsos positivos (benignos con ALTO) | 0 / 120 |
| benignos limpios | 120 |
| tasa de detección (recall) | 3% |
| precisión | 100% |

## Por tipo de ataque

| tipo | casos | detectados | no detectados |
|---|---|---|---|
| skill_injection | 60 | 2 | 58 |

## Falsos negativos (ataques que no dieron ALTO)

| id | tipo | lo que sí vio |
|---|---|---|
| v3-mal-001 | skill_injection | — |
| v3-mal-002 | skill_injection | — |
| v3-mal-003 | skill_injection | — |
| v3-mal-004 | skill_injection | — |
| v3-mal-005 | skill_injection | — |
| v3-mal-006 | skill_injection | — |
| v3-mal-007 | skill_injection | — |
| v3-mal-008 | skill_injection | — |
| v3-mal-009 | skill_injection | — |
| v3-mal-010 | skill_injection | — |
| v3-mal-011 | skill_injection | — |
| v3-mal-012 | skill_injection | — |
| v3-mal-013 | skill_injection | — |
| v3-mal-014 | skill_injection | — |
| v3-mal-015 | skill_injection | — |
| v3-mal-016 | skill_injection | — |
| v3-mal-017 | skill_injection | — |
| v3-mal-018 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-019 | skill_injection | MEDIO: Menciona secretos |
| v3-mal-021 | skill_injection | MEDIO: Menciona secretos |
| v3-mal-023 | skill_injection | — |
| v3-mal-024 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-025 | skill_injection | — |
| v3-mal-026 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-027 | skill_injection | — |
| v3-mal-028 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-029 | skill_injection | — |
| v3-mal-030 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-031 | skill_injection | — |
| v3-mal-032 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-033 | skill_injection | — |
| v3-mal-034 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-035 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-036 | skill_injection | — |
| v3-mal-037 | skill_injection | — |
| v3-mal-038 | skill_injection | — |
| v3-mal-039 | skill_injection | — |
| v3-mal-040 | skill_injection | — |
| v3-mal-041 | skill_injection | — |
| v3-mal-042 | skill_injection | — |
| v3-mal-043 | skill_injection | — |
| v3-mal-044 | skill_injection | — |
| v3-mal-045 | skill_injection | — |
| v3-mal-046 | skill_injection | — |
| v3-mal-047 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-048 | skill_injection | — |
| v3-mal-049 | skill_injection | MEDIO: Envío de datos a URL externa |
| v3-mal-050 | skill_injection | — |
| v3-mal-051 | skill_injection | — |
| v3-mal-052 | skill_injection | — |
| v3-mal-053 | skill_injection | — |
| v3-mal-054 | skill_injection | — |
| v3-mal-055 | skill_injection | — |
| v3-mal-056 | skill_injection | — |
| v3-mal-057 | skill_injection | — |
| v3-mal-058 | skill_injection | — |
| v3-mal-059 | skill_injection | — |
| v3-mal-060 | skill_injection | — |

## Falsos positivos (benignos que dieron ALTO)

Ninguno.

## Benignos con avisos MEDIO (no fallan el CI, pero hacen ruido): 5

| id | reglas |
|---|---|
| v3-benign-012 | MEDIO: Menciona secretos |
| v3-benign-025 | MEDIO: Menciona secretos, MEDIO: Mete datos en un parámetro de la tool |
| v3-benign-026 | MEDIO: Menciona secretos, MEDIO: Mete datos en un parámetro de la tool |
| v3-benign-033 | MEDIO: Menciona secretos |
| v3-benign-041 | MEDIO: Menciona secretos |

## Detectados

| id | tipo | reglas ALTO |
|---|---|---|
| v3-mal-020 | skill_injection | ALTO: Secreto + envío externo (posible robo) |
| v3-mal-022 | skill_injection | ALTO: Secreto + envío externo (posible robo) |

## Conclusión (medido una sola vez, sin cambiar reglas)

- **Por ataque distinto (la cifra que vale): 2 de 34 detectados (6%).** 10 más dieron solo avisos MEDIO y 22 no dieron ningún aviso. Un ataque cuenta como detectado si alguna de sus redacciones dio ALTO.
- **Por texto: 2 de 60 (3%).** Los dos son por "secreto + envío externo". Otros 12 dieron solo avisos MEDIO (10 de envío a URL externa, 2 de secretos), que no hacen fallar el CI. Los 46 restantes no dieron ningún aviso. Son 60 textos y no 68 porque 8 de los 34 ataques traen una sola redacción (el otro campo viene vacío en la fuente); 26 traen dos.
- **Falsas alarmas: 0 de 120 benignos con ALTO.** 5 benignos dieron avisos MEDIO.
- Esto confirma lo que ya sugería el holdout v2 (5/263): el 22/23 del holdout v1 refleja el ajuste, no la detección real. Fuera de los casos con que se ajustaron, las reglas detectan muy poco.
- Por qué, según el paper (no leí los textos maliciosos): estas inyecciones están escritas como pasos normales de una skill (hacer un backup, subir un archivo, mandar un mail) y no usan las frases típicas que buscan las reglas ("ignore previous instructions", "silently", "don't tell the user"). Para distinguirlas hace falta entender la intención, y reglas fijas de texto no pueden.
- Límites de este set:
  - **(a) Los ataques van aislados**, sin la skill que los rodea en el paper. Eso los hace *más fáciles* de detectar que en el paper (no hay texto legítimo alrededor que los diluya), y aun así casi no se detectan. Dentro de una skill real la cifra sería igual o peor.
  - **(b) Este set mide inyección en SKILL.md, no tool poisoning en descripciones MCP.** Los textos MCP del set son solo benignos (miden falsas alarmas). Para tool poisoning haría falta otra fuente; MCPTox lo cubre pero no tiene licencia.
  - Son 34 ataques. La mayoría viene en 2 redacciones parecidas, así que los 60 textos no son independientes; por eso la cifra principal es por ataque.
  - Los benignos son pocos (120), y los SKILL.md vienen del mismo benchmark.
- No se cambió ninguna regla después de medir.
- Nota de proceso: la primera versión de este reporte traía el texto de cada ataque no detectado. Al revisar el formato del reporte se vio por accidente una línea de un texto malicioso (`v3-mal-001`). Después de eso la tabla quedó solo con ids, `scripts/medir_corpus.py` ya no imprime textos de ataque, y ninguna regla cambió.
