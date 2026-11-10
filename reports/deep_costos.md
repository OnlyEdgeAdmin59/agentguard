# Costos de `--deep` (API de Anthropic)

Tope total: $15. Fuente: `usage` de cada respuesta y la tabla de precios de `agentguard/deep.py`.

| fecha | corpus | modelo | prompt | nota | llamadas | tokens entrada | tokens salida | costo |
|---|---|---|---|---|---|---|---|---|
| 2026-11-09 21:31 | tests/corpus | claude-haiku-5-5 | v1 | 1 corrida(s) | 67 | 70434 | 7724 | $0.0109 |
| 2026-11-09 21:31 | tests/corpus_holdout | claude-haiku-5-5 | v1 | 1 corrida(s) | 46 | 49619 | 6313 | $0.0081 |
| 2026-11-09 21:33 | tests/corpus_holdout_v2 | claude-haiku-5-5 | v1 | 1 corrida(s) | 662 | 698947 | 63333 | $0.1016 |
| 2026-11-09 21:34 | tests/corpus | claude-haiku-5-5 | v2 | 3 corrida(s) | 201 | 247218 | 21064 | $0.0353 |
| 2026-11-09 21:35 | tests/corpus_holdout | claude-haiku-5-5 | v2 | 3 corrida(s) | 138 | 173622 | 20149 | $0.0274 |
| 2026-11-09 21:39 | tests/corpus_holdout_v2 | claude-haiku-5-5 | v2 | 3 corrida(s) | 1986 | 2450544 | 211877 | $0.3510 |
| 2026-11-09 21:47 | tests/corpus | claude-haiku-5-5 | v3 | 3 corrida(s) | 201 | 252480 | 22110 | $0.0363 |
| 2026-11-09 21:47 | tests/corpus_holdout | claude-haiku-5-5 | v3 | 3 corrida(s) | 138 | 177291 | 20267 | $0.0279 |
| 2026-11-09 21:52 | tests/corpus_holdout_v2 | claude-haiku-5-5 | v3 | 3 corrida(s) | 1986 | 2504130 | 201424 | $0.3511 |
| 2026-11-09 21:52 | tests/corpus | claude-sonnet-5-5 | v3 | 1 corrida(s) | 67 | 84136 | 6663 | $0.2349 |
| 2026-11-09 21:53 | tests/corpus_holdout | claude-sonnet-5-5 | v3 | 1 corrida(s) | 46 | 59154 | 4582 | $0.1641 |
| 2026-11-09 21:55 | tests/corpus_holdout_v2 | claude-sonnet-5-5 | v3 | 1 corrida(s) | 662 | 834744 | 77670 | $2.4462 |
| 2026-11-09 22:11 | tests/corpus_holdout_v3 | claude-haiku-5-5 | v3 | ciego final | 180 | 443390 | 19672 | $0.0542 |
| 2026-11-09 23:05 | ~/.claude SKILL.md (ruido) | claude-haiku-5-5 | v3 | skills reales | 1894 | 21888660 | 564298 | $2.4710 |
