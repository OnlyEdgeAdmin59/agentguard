# agentguard

Seguridad para agentes de IA que usan skills y servidores MCP. Funciona en tu máquina, sin cuenta y sin dependencias (Python 3.9+).

- `scan`: busca instrucciones ocultas (tool poisoning) en skills (`SKILL.md`) y herramientas MCP (JSON).
- `lock` / `verify`: avisa si un conector cambió después de aprobarlo (rug pull).
- `cve`: revisa los servidores MCP instalados contra vulnerabilidades conocidas (OSV.dev).
- `trifecta`: avisa si tu configuración junta la "tríada letal" (datos privados + contenido no confiable + salida hacia afuera).
- `audit`: junta todo en un reporte de auditoría en Markdown.

**No detecta todo.** En un set ciego independiente (Skill-Inject, MIT), `scan` marcó como ALTO 2 de 60 textos de ataque (3%) y con algún aviso 14 (23%), sin falsas alarmas ALTAS en 120 benignos. Úsalo como primer filtro: `cve`, `trifecta` y `lock`/`verify` no dependen de esas reglas. Que no haya hallazgos no prueba que algo sea seguro. Ver [CHANGELOG.md](CHANGELOG.md).

## Instalación
```bash
pip install agentguard-scan
```
O sin instalar nada permanente:
```bash
uvx --from agentguard-scan agentguard scan ./mis-skills
```

## Uso
```bash
agentguard scan   carpeta [--all]      # hallazgos ALTO hacen fallar con código 1
agentguard lock   carpeta              # guarda huellas en agentguard.lock.json
agentguard verify carpeta              # código 1 si algo cambió desde el lock
agentguard cve    [carpeta | archivo_config]
agentguard trifecta [carpeta | archivo_config] [--tools carpeta]
agentguard audit  [--skills carpeta] [--config archivo] [--tools carpeta] [--sin-red] [--out reporte.md]
```

### Idioma / Language
La salida está en español por defecto. Para inglés, agrega `--lang en` a cualquier comando o usa la variable de entorno `AGENTGUARD_LANG=en`. El reporte de `audit` también sale en inglés (ejemplo: [reports/audit_example_en.md](reports/audit_example_en.md)).

Output is in Spanish by default. For English, add `--lang en` to any command or set `AGENTGUARD_LANG=en`. `audit` also accepts `--project` and `--offline` (aliases of `--proyecto` and `--sin-red`).
```bash
agentguard scan ./my-skills --lang en
agentguard audit --skills ~/.claude/skills --offline --out report.md --lang en
```

### cve
```bash
agentguard cve                                  # configs de Claude Desktop, Claude Code, Cursor y VS Code
agentguard cve ~/.cursor/mcp.json               # un archivo de config
```
```
paquete                                  versión      CVE                    severidad  corregida
mcp-remote                               0.1.15       CVE-2025-6514          CRITICAL   0.1.16
[INFO] Claude Desktop · fetch: mcp-server-fetch (PyPI) — versión no fijada (se ejecuta la última)
```
Lee paquete y versión de cada servidor (`npx pkg@1.2.3`, `uvx pkg==1.2.3`, …) y consulta [OSV.dev](https://osv.dev).
A OSV solo se envía nombre, ecosistema y versión; nunca descripciones de tools ni rutas.
Sale con 1 si hay vulnerabilidades y con 2 si no hay red.

### trifecta
```bash
agentguard trifecta                             # todas las configs, por cliente y por proyecto
agentguard trifecta .mcp.json --tools ./tools   # --tools: <servidor>.json con la salida de tools/list
```
```
== Claude Code · proyecto /home/demo/app: 3 servidor(es)
[ALTO] TRÍADA LETAL: esta configuración junta las tres capacidades.
  - Lee datos privados: archivos (tabla: lee y escribe archivos locales)
  - Trae contenido no confiable: buscador (tabla: trae resultados de búsqueda web)
  - Envía hacia afuera: avisos (heurística: webhook, notifier (comando) — confirmar a mano)
Para romperla, quita una de estas opciones (lo que menos servidores toca):
  • archivos  → ya nadie lee datos privados
```
Cada servidor se clasifica con una tabla de servidores conocidos (`agentguard/trifecta/known.json`) o, si no está, por heurística; el reporte dice cuál.
Cada proyecto se revisa con los servidores globales más los suyos, no mezclado con otros proyectos.

### audit
```bash
agentguard audit --skills ~/.claude/skills --out auditoria.md
```
Genera un reporte con resumen ejecutivo, hallazgos por severidad, cómo arreglar cada uno y una sección de revisión manual para completar a mano.
`--sin-red` se salta la consulta a OSV.dev.

## GitHub Action
```yaml
- uses: actions/checkout@v5
- uses: OnlyEdgeAdmin59/agentguard@v0.4.0
```
Falla el build si hay hallazgos ALTOS y los marca en la línea del PR.
Con `lang: en` la salida y las anotaciones salen en inglés:
```yaml
- uses: OnlyEdgeAdmin59/agentguard@v0.4.0
  with:
    lang: en
```
