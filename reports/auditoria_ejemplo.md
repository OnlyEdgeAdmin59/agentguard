# Auditoría de seguridad de agentes (AgentGuard)

Fecha: 2026-11-02

Alcance: ejemplo con fixtures: skills `ejemplos`, config `tests/fixtures/cve/claude_desktop_config.json`, OSV guardado

## Resumen ejecutivo

**Riesgo general: Alto.**

- **scan**: 1 archivo(s) revisados, 6 hallazgo(s), 2 ALTO(s).
- **cve**: 6 servidor(es), 4 con versión fija consultados en OSV.dev, 1 vulnerabilidad(es).
- **trifecta**: tríada letal en 1 de 1 alcance(s) (global y cada proyecto).

| severidad | hallazgos |
|---|---|
| Crítico | 1 |
| Alto | 3 |
| Medio | 3 |
| Bajo | 0 |
| Info | 2 |

## Hallazgos por severidad

### Crítico (1)

**H-01 · CVE-2025-6514 en mcp-remote 0.1.15** — cve · npm
- Detalle: GHSA-6xpm-ggf7-wc3p · severidad CRITICAL · mcp-remote exposed to OS command injection via untrusted MCP server connections
- Cómo arreglar: Actualiza mcp-remote a 0.1.16.

### Alto (3)

**H-02 · Pide ocultar algo al usuario** — scan · ejemplos/malicioso_tools.json:1
- Detalle: «Do not tell the user»
- Cómo arreglar: Elimina la orden de ocultarle cosas al usuario. Si viene de un tercero, trátalo como malicioso: desinstálalo y repórtalo.

**H-03 · Secreto + envío externo (posible robo)** — scan · ejemplos/malicioso_tools.json:1
- Detalle: «.ssh → send it to https://»
- Cómo arreglar: Revísalo ya: pide leer credenciales y sacarlas. Desinstálalo, cambia las llaves que menciona y repórtalo al autor o al registro.

**H-04 · Tríada letal** — trifecta · archivo · global
- Detalle: Lee datos privados: filesystem (tabla), git (tabla), docker (tabla); Trae contenido no confiable: remote-ok (heurística), fetch (tabla), win-wrapped (tabla), docker (tabla); Envía hacia afuera: fetch (tabla), win-wrapped (tabla), docker (tabla)
- Cómo arreglar: Quita una de estas opciones: filesystem, git, docker | fetch, win-wrapped, docker. docker junta las tres solo: limita sus tools (solo lectura, repos permitidos).

### Medio (3)

**H-05 · Menciona secretos** — scan · varios
- Detalle: 2 veces en 1 archivo(s): ejemplos/malicioso_tools.json:1, ejemplos/malicioso_tools.json:1
- Cómo arreglar: Confirma que solo explica dónde poner la llave y no le pide al modelo leerla.

**H-06 · Envío de datos a URL externa** — scan · ejemplos/malicioso_tools.json:1
- Detalle: «send it to https://»
- Cómo arreglar: Confirma que el dominio es del autor y que el envío hace falta; si no, quítalo.

**H-07 · Etiquetas de urgencia para el modelo** — scan · ejemplos/malicioso_tools.json:1
- Detalle: «<IMPORTANT>»
- Cómo arreglar: Quita etiquetas tipo <IMPORTANT> dirigidas al modelo; una descripción honesta no las necesita.

### Info (2)

**H-08 · mcp-server-fetch (PyPI): versión no fijada (se ejecuta la última)** — cve · archivo · fetch
- Cómo arreglar: Fija la versión exacta (`pkg@1.2.3` / `pkg==1.2.3`) para que no cambie sin que lo apruebes.

**H-09 · docker: comando 'docker' no indica un paquete npm/PyPI** — cve · archivo · docker
- Cómo arreglar: Revísalo a mano: no se puede consultar en OSV.

## Revisión manual

> Para completar por quien audita. Lo automático no reemplaza esta parte.

- [ ] Hallazgos confirmados y descartados (por ID):
- [ ] Permisos reales de cada servidor (tokens, carpetas, cuentas):
- [ ] Origen y mantenedor de cada servidor (¿cambió de dueño o de repo?):
- [ ] Tools revisadas a mano (salida de tools/list):
- [ ] Skills de terceros leídas completas:
- [ ] Conclusión:

Auditor: ________ · Fecha: ________

## Límites

- En un set ciego independiente (Skill-Inject, MIT: 34 ataques en 60 textos), las reglas solas marcaron como ALTO 2 de 34 ataques (6%); con `--deep` (Claude Haiku), 31 de 34 (91%). En 120 benignos, `--deep` dio 2 falsas alarmas ALTAS y 11 tuvieron algún aviso (9%). En 1170 SKILL.md reales, `--deep` marcó 30 como ALTO (2,6%, todos falsas alarmas al revisarlos a mano) y el 39% tuvo algún aviso. Es una sola medición; el modelo puede variar entre corridas. `--deep` envía el texto a Anthropic y necesita ANTHROPIC_API_KEY. Que no haya hallazgos no prueba que algo sea seguro.
- `cve`, `trifecta` y `lock`/`verify` no dependen de las reglas de `scan` ni de `--deep`.
- `trifecta` clasifica con una tabla de servidores conocidos y, si no están, con heurística por palabras; lo heurístico hay que confirmarlo a mano.
- `cve` solo encuentra vulnerabilidades publicadas en OSV.dev para paquetes con versión fija.
- No se ejecutó ningún servidor.
