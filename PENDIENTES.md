# Pendientes para la PC

1. Descomprimir agentguard.zip.
2. Probar local en Windows:
   python agentguard.py scan ejemplos
   python agentguard.py lock ejemplos
   python agentguard.py verify ejemplos
3. Crear repo público "agentguard" en GitHub y subir la carpeta.
4. Crear release con tag v0.1.0.
5. En ejemplo-workflow/agentguard.yml cambiar TU_USUARIO por tu usuario.
6. Copiar ese workflow en .github/workflows/ de un repo tuyo con skills y hacer push.
7. Confirmar que GitHub marca los hallazgos en el PR.

Después: módulo canary → firewall → API (FastAPI, versiones fijas) → registro "verificado".
Evitar: LiteLLM, mcp-remote 0.1.32–0.1.38, MCP TS SDK < 2.3.0, Next.js < 16.4.1 / 15.5.28.
