# Corpus de prueba (Fase 0)

Un caso por archivo JSON:

| campo | qué es |
|---|---|
| `id` | identificador único (`benign-NNN`, `mal-NNN`) |
| `tipo` | `herramienta_mcp`, `skill` (benignos); `instrucciones_ocultas`, `exfiltracion`, `tool_shadowing`, `unicode_invisible`, `rug_pull` (maliciosos) |
| `formato` | `mcp` (va como `description` de una tool en un JSON MCP) o `skill` (va como `SKILL.md`) |
| `texto` | el texto a revisar (en `rug_pull`, la versión que cambió) |
| `texto_antes` | solo `rug_pull`: la versión aprobada original |
| `resultado_esperado` | `limpio` (no debe dar ALTO) o `alerta` (debe dar al menos un ALTO; en `rug_pull`, `verify` debe avisar) |

Los caracteres invisibles están escapados (`​`) para que se vean al revisar el archivo.
Medir: `python scripts/medir_corpus.py` → `reports/fase0.md`.
