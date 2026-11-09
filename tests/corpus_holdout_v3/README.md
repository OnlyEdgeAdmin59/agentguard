# Holdout v3: skill-inject + modelcontextprotocol/servers

Convertido con `python scripts/importar_holdout_v3.py`. Los textos se copiaron tal cual.

| parte | fuente | licencia | commit |
|---|---|---|---|
| maliciosos (60) | https://github.com/aisa-group/skill-inject (paper: https://arxiv.org/abs/2602.20156) | MIT | `b07cfdb2299b07ceb156c227b4b845359bbac363` |
| benignos: SKILL.md (45) | https://github.com/aisa-group/skill-inject `data/skills/` | MIT; algunas skills Apache 2.0 (su LICENSE.txt). Se excluyen las "All rights reserved" | `b07cfdb2299b07ceb156c227b4b845359bbac363` |
| benignos: tools MCP (75) | https://github.com/modelcontextprotocol/servers | MIT / Apache 2.0 | `36380287ed3b15d115b55f546617d723072b1296` |

Maliciosos: las inyecciones "obvias" del benchmark, cada una en sus dos redacciones (`description_injection` y `line_injection`), cada una sola como SKILL.md. Son 34 ataques distintos: 26 con dos redacciones y 8 con una sola (el otro campo viene vacío en la fuente), en total 60 textos. Se excluyen las 8 que el paper reclasificó como contextuales y los casos contextuales (doble uso). En el paper la inyección va dentro de una skill más larga; acá va sola, así que es más fácil de ver que en el original.

Benignos: SKILL.md limpios del mismo benchmark (formato `skill`) y las descripciones de tools de los servidores de referencia de MCP (formato `mcp`): todo `description` que sigue a un `title` en TypeScript (incluye algunos campos de esquema, p. ej. del formulario de elicitation del servidor `everything`) y el `description` de los decoradores `@*.tool` en Python. Las descripciones armadas con f-strings no se incluyen.

Holdout ciego: no se usa para ajustar reglas. Se mide una sola vez.
