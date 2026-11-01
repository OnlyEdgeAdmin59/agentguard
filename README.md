# agentguard

Seguridad para agentes de IA: detecta instrucciones ocultas (tool poisoning) en skills y herramientas MCP, y alerta si un conector cambió después de aprobarlo (rug pull).

## GitHub Action
```yaml
- uses: actions/checkout@v4
- uses: OnlyEdgeAdmin59/agentguard@v0.1.0
```
Falla el build si hay hallazgos ALTOS y los marca en la línea del PR.

## CLI
```
python agentguard.py scan   carpeta
python agentguard.py lock   carpeta
python agentguard.py verify carpeta
```
Sin dependencias: solo Python 3.9+.
