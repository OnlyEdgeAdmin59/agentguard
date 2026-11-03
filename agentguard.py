"""Atajo para correr agentguard sin instalarlo: `python agentguard.py scan <carpeta>`.

El código vive en el paquete agentguard/ (scanner, cli, cve). Este archivo se queda porque
action.yml lo llama con `python3 "$GITHUB_ACTION_PATH/agentguard.py"`.
"""
from agentguard.cli import run

if __name__ == "__main__":
    run()
