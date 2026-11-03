# Estado de la versión publicada (2026-11-02)

Comando: `pip download agentguard-scan==0.1.4 --no-deps` (sin instalar). Wheel inspeccionado como zip, sin ejecutarlo.

| Dato | Resultado |
|---|---|
| Archivo | `agentguard_scan-0.1.4-py3-none-any.whl` (9213 bytes) |
| SHA-256 | `3437513e629863e5ce7ca2de5dc8e4b86e96d66d44e95ec13e1af07c848d83d2` |
| Contenido | solo `agentguard.py` (8172 bytes) + metadatos y LICENSE |
| ¿Incluye `lock`? | **Sí** (`cmd_lock`, `fingerprints`, `LOCK_NAME`) |
| ¿Incluye `verify`? | **Sí** (`cmd_verify`) |
| Comandos | `COMMANDS = {"scan", "lock", "verify"}` |
| ¿Igual al tag `v0.1.4` del repo? | **Sí**, idéntico (ignorando fin de línea) |

## Ojo
- En PyPI **solo existe la 0.1.4**. El repo ya está en **0.1.5** (tag `v0.1.5`: menos falsas alarmas, `--all`, fix secreto+envío con `.env`), pero esa versión **no se publicó**. Quien instale con pip recibe la 0.1.4, sin esas mejoras.
- La 0.1.4 no tiene `--all` ni los filtros de contexto de la 0.1.5.
