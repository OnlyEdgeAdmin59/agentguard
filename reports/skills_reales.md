# Falsas alarmas en skills reales (`~/.claude`, 2026-11-02)

Chequeo extra, fuera del corpus: `agentguard scan ~/.claude` (2983 archivos .md/.json; excluye node_modules, CHANGELOG, LICENSE).
No hay ataques conocidos ahí, así que cada ALTO nuevo es casi seguro una falsa alarma. Solo se guardan los conteos (sin rutas).

| | antes (main) | primer intento de reglas | final |
|---|---|---|---|
| ALTO | 1 | **134** | 1 |
| MEDIO | 1568 | 6944 | 1618 |

- El ALTO que queda es el mismo de antes: un documento que cita, dentro de un comentario HTML, un ataque de ejemplo.
- **Lección:** el corpus decía 0 falsos positivos y en skills reales el primer intento daba 134. Las causas eran "silently …" descriptivo
  ("X silently fails", "never silently add"), "instructions for the AI" en documentación, "when the X tool returns…" en docs,
  "don't tell the user **to** …", y la palabra "file" como señal de peligro.
- MEDIO por regla (final): secretos 1455, etiquetas de urgencia 43, ocultar 40, a escondidas 24, envío 20, anular 20, parámetro 15.
