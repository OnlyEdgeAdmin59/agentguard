# Resumen: rama `feat/fase0-fase1` (2026-11-02)

Todo en commits locales. Sin push, sin release, sin PyPI, sin tocar `.github/workflows` ni secretos, sin borrar archivos existentes.
Suite completa: `python -m unittest discover tests` → **24 tests, OK**.

## Qué se hizo
1. **Versión publicada** (`reports/estado.md`): `agentguard-scan==0.1.4` en PyPI **sí incluye `lock` y `verify`** y es idéntica al tag `v0.1.4`. Ojo: PyPI solo tiene la 0.1.4; la **0.1.5 del repo nunca se publicó**.
2. **Corpus Fase 0** (`tests/corpus/`): 34 benignos (tools MCP y skills variadas, incluidas trampas: docs de seguridad, `curl` con su propio API key, emojis, comentarios HTML normales) y 33 maliciosos (instrucciones ocultas, exfiltración, tool shadowing, unicode invisible/homoglifos, rug pull, base64). Un JSON por caso con `id, tipo, texto, resultado_esperado` (+ `formato`, y `texto_antes` en rug pull).
3. **Medición** (`scripts/medir_corpus.py` → `reports/fase0.md`): corre el scanner tal cual, sin cambiar reglas.
4. **Módulo CVE** (`agentguard/cve/`): inventario de configs MCP de Claude Desktop, Claude Code (`~/.claude.json` + proyectos + `.mcp.json`), Cursor y VS Code (`mcp.json` y `settings.json` con comentarios) en Windows/macOS/Linux; saca paquete/ecosistema/versión de `npx`, `bunx`, `pnpm dlx`, `npm exec`, `uvx`, `uv tool run`, `pipx run`, `cmd /c`. Consulta OSV.dev (`querybatch` + detalle por ID) enviando **solo nombre, ecosistema y versión** (hay un test que lo verifica). Comando nuevo: `agentguard cve [carpeta | archivo]` → paquete, versión, CVE, severidad, versión corregida; sale con 1 si hay vulnerabilidades, 2 si no hay red.

## Resultados de la medición
| | |
|---|---|
| Ataques detectados | **17 / 33 (52%)** |
| Falsos positivos | **0 / 34** |
| Benignos con ruido MEDIO | 9 / 34 |

Por tipo: unicode 5/6, exfiltración 5/9, instrucciones ocultas 3/9, **tool shadowing 0/5**, rug pull 4/4 (pero `verify` avisa de *cualquier* cambio; el `scan` del texto nuevo solo lo pilla 1/4).

Fallos que más importan:
- **mal-001, el ejemplo clásico de tool poisoning** (`<IMPORTANT>` + leer `~/.ssh/id_rsa` + "do not mention this to the user") queda solo en MEDIO: la comilla de `'sidenote'` hace creer al filtro que es una cita.
- Nada en español (`Ignora todas las instrucciones…`, `envíalo a https://…`).
- Paráfrasis: "disregard your safety guidelines", "Note to the AI model", `<system>…`.
- Homoglifos cirílicos (`Ignоre`), base64 con la orden escondida (solo MEDIO), imagen markdown que filtra datos por la URL.
- Exfiltración por parámetro ("pon el OPENAI_API_KEY en el parámetro license").

## Qué falta
- Cambiar reglas (no se tocaron, a propósito): la Fase 0 solo midió.
- `cve` no resuelve versiones no fijadas (`npx pkg` sin versión = baja la última); se reportan como INFO y no se consultan.
- Severidad: usa la etiqueta de OSV/GHSA; si solo hay vector CVSS lo muestra tal cual (no calcula el puntaje).
- No se probó contra la API real de OSV (todos los tests son sin red). El wheel se construyó e instaló en un venv temporal y `agentguard cve` funciona instalado.
- Estructura: `agentguard.py` sigue siendo un solo archivo y se le agregó `__path__` para que `agentguard.cve` funcione sin mover nada. Lo limpio sería convertirlo en paquete `agentguard/__init__.py` (implica mover el archivo y ajustar `action.yml`).

## Bloqueos
Ninguno. No hizo falta `BLOCKERS.md`.

## 3 siguientes pasos recomendados
1. **Arreglar los falsos negativos más graves sin subir falsos positivos**: mal-001 (filtro de comillas), español, tool shadowing (frases tipo "when the X tool is used…", "instead of the official tool"), homoglifos. Volver a correr `medir_corpus.py` después de cada regla y no aceptar ningún falso positivo nuevo.
2. **Probar `agentguard cve` una vez contra OSV real** en tu máquina y, si va bien, publicar la 0.1.5/0.1.6 en PyPI (eso lo decidís vos: crear el release dispara la publicación).
3. **Que `verify` también corra `scan` sobre lo que cambió**, para que un rug pull se marque ALTO por su contenido y no solo como "cambió".
