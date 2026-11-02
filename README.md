# agentguard

Seguridad para agentes de IA: detecta instrucciones ocultas (tool poisoning) en skills y herramientas MCP, y alerta si un conector cambió después de aprobarlo (rug pull).

## GitHub Action
```yaml
- uses: actions/checkout@v5
- uses: OnlyEdgeAdmin59/agentguard@v0.1.5
```
Falla el build si hay hallazgos ALTOS y los marca en la línea del PR.

## CLI
```
python agentguard.py scan   carpeta [--all]
python agentguard.py lock   carpeta
python agentguard.py verify carpeta
python agentguard.py cve    [carpeta_del_proyecto | archivo_config]
```
`cve` lee las configs MCP de Claude Desktop, Claude Code, Cursor y VS Code, saca paquete y versión
(`npx pkg@1.2.3`, `uvx pkg==1.2.3`) y consulta [OSV.dev](https://osv.dev). A OSV solo se envía
nombre, ecosistema y versión; nunca descripciones de tools ni rutas. Sale con 1 si hay vulnerabilidades.
Sin dependencias: solo Python 3.9+.
