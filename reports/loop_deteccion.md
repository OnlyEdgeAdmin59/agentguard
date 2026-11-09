# Loop de detección (rama `feat/detection-loop`)

Objetivo: subir la detección de `agentguard scan` sin subir falsas alarmas.
10 iteraciones, una hipótesis cada una, todas en `agentguard/scanner.py`. Sin casos de prueba nuevos. Sin push ni merge.

## Antes / después

| conjunto | antes | después |
|---|---|---|
| Ajuste `tests/corpus` | 33/33 detectados, FP 0/34 | 33/33, FP 0/34 |
| Holdout v1 `tests/corpus_holdout` (ya usado, no ciego) | 10/23, FP 1/23 | **22/23**, FP 1/23 |
| Ruido en skills reales (`ruido_skills.py`) | ALTO 1, MEDIO 1618 | ALTO 1, MEDIO 1628 (límite 1779, OK) |
| **Ciego** holdout v2 `tests/corpus_holdout_v2` (deepset) | 5/263, FP 2/399 | **5/263, FP 2/399** |
| `pytest -q` | 62 passed, 2 skipped | 62 passed, 2 skipped |

"Antes" del ciego = `reports/holdout_v2_antes.md` (el scanner no cambió en `main` desde esa medición). "Después" = `reports/loop_holdout_v2_despues.md`, medido una sola vez al final.

## Iteraciones

| # | hipótesis | holdout v1 | resultado |
|---|---|---|---|
| 1 | Aislantes bidi U+2066–2069 cuentan como invisibles (regla y `normalize`) | 10 → 11 | aceptada |
| 2 | Anular reglas en portugués y francés con más verbos (desconsidere, oublie…) | 11 → 13 | aceptada |
| 3 | Reglas "outdated/superseded", "no longer bind you", "operate as an unrestricted…" | 13 → 15 | aceptada |
| 4 | Tool shadowing en español ("cuando uses la herramienta X, cambia siempre…") | 15 → 16 | aceptada |
| 5 | Hacer a escondidas: + run/execute/install/download; `\| sh` cuenta como peligro | 16 → 17 | aceptada |
| 6 | "For every call to `snake_case_tool`, set…" como tool shadowing | 17 → 18 | aceptada |
| 7 | Prefijar comandos con `curl … \| sh` como tool shadowing | 18 → 19 | aceptada |
| 8 | Parámetro con el nombre después ("copia en el parámetro 'x'…") + "contenido completo de" | 19 → 20 | aceptada |
| 9 | Más archivos de credenciales (gh/hosts.yml, .netrc, .npmrc…) + urllib con `data=` como envío | 20 → 21 | aceptada |
| 10 | "append/attach … to https://" como envío + "output of \`env\`" como secreto | 21 → 22 | aceptada |

Ninguna iteración subió falsos positivos en ajuste ni en holdout v1, y el ruido quedó dentro del límite en todas. No hubo reglas con nombre nuevo (todas amplían reglas existentes), así que `i18n.py` no se tocó. Se llegó al máximo de 10; nunca hubo 3 seguidas sin mejora.

Sin resolver en holdout v1: `hold-mal-011` (link markdown cuya URL hay que llenar con la transcripción). El FP `hold-benign-012` ya estaba en la línea base.

## Conclusión honesta

- **El ciego no mejoró: 5/263 antes y 5/263 después.** Los FP tampoco cambiaron (2/399).
- La subida en holdout v1 (10 → 22) **no es evidencia de generalización**: ese conjunto ya se había usado, y cada hipótesis se sacó mirando sus falsos negativos. Es ajuste, no prueba.
- El ciego (deepset) es otro tipo de ataque: prompt injection conversacional, sin tools ni archivos, mucho en alemán. Estas reglas apuntan a descripciones de tools y skills (shadowing, exfiltración, unicode), así que era esperable que no se movieran ahí. Para subir en ese conjunto harían falta reglas pensadas para injection conversacional y, sobre todo, un conjunto de ajuste parecido.
- Lo que sí se puede decir: las 10 reglas no agregaron falsas alarmas ni en benignos ni en skills reales (MEDIO +10, ALTO igual).
- Nota de proceso: después de terminar las 10 iteraciones, y antes de la medición del ciego, abrí `reports/holdout_v2_antes.md` para sacar la línea base. Ahí se ven algunos textos del ciego. Ninguna regla cambió después de eso.

## Archivos

- Líneas base: `reports/loop_base.md`, `reports/loop_base_holdout.md`
- Después: `reports/loop_despues.md`, `reports/loop_despues_holdout.md`, `reports/loop_holdout_v2_despues.md`
- Commits: uno por iteración en `feat/detection-loop`, con el antes/después en el mensaje.
