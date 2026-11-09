# Cambios

## Sin publicar

### Documentación
- Nuevo set ciego independiente (holdout v3: Skill-Inject, MIT, más tools de modelcontextprotocol/servers como benignos). Resultado en `reports/holdout_v3.md` (2 de 34 ataques con ALTO). La frase de detección del README y de "Límites" en `audit` pasa a ser:
  > En un set ciego independiente (Skill-Inject, MIT: 34 ataques en 60 textos), `scan` marcó como ALTO 2 de 34 ataques (6%) y con algún aviso 12 (35%), sin falsas alarmas ALTAS en 120 benignos (5 con aviso MEDIO). Úsalo como primer filtro: `cve`, `trifecta` y `lock`/`verify` no dependen de esas reglas. Que no haya hallazgos no prueba que algo sea seguro.

## 0.4.0

### Cambiado
- **Reglas de `scan` ampliadas** (sin reglas con nombre nuevo):
  - Aislantes bidi (U+2066–2069) cuentan como caracteres invisibles.
  - Anular instrucciones: más verbos en portugués y francés, y frases como "the guidance you received is outdated" o "no longer binds you".
  - Tool shadowing: variante en español ("cuando uses la herramienta X…"), "for every call to `tool_name`, set…" y anteponer `curl … | sh` a los comandos.
  - Hacer algo a escondidas: incluye run/execute/install/download; `| sh` cuenta como peligro.
  - Exfiltración: parámetro con el nombre después ("en el parámetro 'x'"), más archivos de credenciales (gh/hosts.yml, .netrc, .npmrc, .pypirc, .docker/config.json, .kube/config), urllib con `data=` como envío, "append … to https://" y la salida de `env`.
- **Sin falsas alarmas nuevas**: 0/34 en el corpus de ajuste y 1/23 en el holdout v1 (igual que antes). En skills reales, ALTO sigue en 1 y MEDIO pasó de 1618 a 1628.
- Detección: holdout v1 de 10/23 a 22/23. **El holdout v1 ya no es ciego**: las reglas se ajustaron mirando sus fallos, así que esa cifra no prueba que generalicen. En el benchmark independiente (deepset) no hubo cambio. Detalle en `reports/loop_deteccion.md`.

## 0.3.0

### Nuevo
- **Salida en inglés**: `--lang en` en cualquier comando o `AGENTGUARD_LANG=en`. Traduce scan, lock/verify, cve, trifecta y el reporte de `audit` completo (incluye cómo arreglar cada hallazgo y los motivos de la tabla de servidores conocidos). La lógica interna no cambia y la salida en español queda idéntica.
- `audit` acepta `--project` y `--offline` como alias de `--proyecto` y `--sin-red`.
- GitHub Action: input `lang` (`es` o `en`).
- Reporte de ejemplo en inglés: `reports/audit_example_en.md`.

## 0.2.0 (sin publicar todavía)

### Nuevo
- **`agentguard cve`**: lee las configs MCP de Claude Desktop, Claude Code, Cursor y VS Code (Windows, macOS, Linux), saca paquete y versión de cada servidor (`npx pkg@1.2.3`, `uvx pkg==1.2.3`, `pipx`, `cmd /c`, etc.) y consulta [OSV.dev](https://osv.dev). A OSV solo se envía nombre, ecosistema y versión. Avisa cuando la versión no está fijada. Sale con código 1 si hay vulnerabilidades y con código 2 si no hay red.
- **`agentguard trifecta`**: avisa cuando una misma configuración junta la "tríada letal": leer datos privados + traer contenido no confiable + enviar hacia afuera.
  - Clasifica con una tabla curada de 20 servidores conocidos y, si el servidor no está, con heurística por nombre, comando, variables de entorno y tools (`--tools <carpeta>`). Siempre dice si cada dato salió de la tabla o de la heurística.
  - Agrupa por alcance real: la config global y cada proyecto por separado (un proyecto hereda los globales).
  - Dice qué servidor aporta cada capacidad y qué quitar para romper la tríada.
- **`agentguard audit`**: genera un reporte de auditoría en Markdown que junta scan, cve y trifecta. Incluye resumen ejecutivo, hallazgos por severidad, cómo arreglar cada uno y una sección de revisión manual.
- `agentguard --version`.

### Cambios
- **Paquete reestructurado**: `agentguard/` con `scanner`, `cli`, `cve`, `trifecta` y `audit`. Se quitó el truco `__path__`. `agentguard.py` queda como atajo para la GitHub Action. La versión vive en un solo lugar (`agentguard/__init__.py`).
- **Mejoras de detección en `scan`**:
  - Comillas: un apóstrofo suelto ya no baja un ataque a MEDIO.
  - Tool shadowing.
  - Reglas en español, portugués y francés.
  - Normalización antes de analizar: caracteres tag, bidi, invisibles, ancho completo y homoglifos cirílicos/griegos.
  - Frases reformuladas, como imagen Markdown que filtra datos o base64 que esconde una orden.

### Qué tan bien detecta (medido, no prometido)
| conjunto | detecta | falsos positivos |
|---|---|---|
| Corpus propio (se usó para ajustar las reglas) | 33/33 | 0/34 |
| **Holdout ciego v1** (nunca se usó para ajustar) | **10/23 (43%)** | 1/23 |
| Holdout v2: [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections) (inyección directa de chat, no tool poisoning) | 5/263 (2%) | 2/399 |

- **AgentGuard no detecta todo.** Las reglas fijas atrapan formas conocidas y se escapa más de la mitad de los ataques nuevos. Úsalo como una capa más, no como garantía.
- `verify` sí avisa de cualquier cambio después de `lock`, pero no juzga si el cambio es malo.

## 0.1.4
- `lock` / `verify` contra rug pulls, GitHub Action con anotaciones en el PR.
