# Ajuste de `--deep`: resumen (2026-11-09)

Solo columna "solo deep". Haiku: rango de 3 corridas. Sonnet: 1 corrida. Holdout v3 (Skill-Inject) sin medir.
Alerta = ALTO. Aviso = ALTO o MEDIO. Detalle en `reports/deep_ajuste_*.md`; costos en `reports/deep_costos.md`.

| set | métrica | Haiku prompt v1 | Haiku prompt v2 | **Haiku prompt v3** | Sonnet prompt v3 |
|---|---|---|---|---|---|
| corpus (33 mal / 34 ben) | ataques con ALTO | 30 | 31–32 | **31–32** | 27 (5 rechazos) |
| | benignos con ALTO | 0 | 0 | **0** | 0 |
| | benignos con aviso | 2 | 2 | **1** | 0 |
| holdout (23 / 23) | ataques con ALTO | 23 | 23 | **23** | 16 (7 rechazos) |
| | benignos con ALTO | 0 | 0–1 | **0** | 0 |
| | benignos con aviso | 2 | 1–3 | **0–2** | 0 |
| v2 deepset (263 / 399) | ataques con ALTO | 127 (48%) | 164–168 | **165–167 (63%)** | 177 (67%) |
| | ataques con aviso | 182 (69%) | — | **207–210 (79%)** | 227 (86%) |
| | benignos con ALTO | 0 | 2–3 | **0** | 0 |
| | benignos con aviso | 0 | 164–181 | **0** | 2 |

- v2 rechazado: subió los avisos falsos (0 → ~43% en benignos de v2).
- v3 aceptado: más detecciones que v1 y ninguna falsa alarma de más.
- Sonnet se negó a responder (`stop_reason: refusal`) en 13 ataques de corpus+holdout; quedan como
  "INFO: sin veredicto", nunca como limpio. Cuesta ~7 veces más que Haiku.

Recomendación: `claude-haiku-5-5` con prompt v3 como default. Sonnet no se ofrece como mejora.

Gasto del ajuste: $3.79 de $15.
