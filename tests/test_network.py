"""Test "network": consulta OSV.dev de verdad. No corre por defecto.
Correr: AGENTGUARD_NETWORK=1 python -m unittest tests.test_network -v
Solo se envía nombre, ecosistema y versión de un paquete público (mcp-remote 0.1.15).
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentguard.cve import osv  # noqa: E402
from agentguard.cve.inventory import Package  # noqa: E402

NETWORK = os.environ.get("AGENTGUARD_NETWORK") == "1"


@unittest.skipUnless(NETWORK, "network: definir AGENTGUARD_NETWORK=1 para consultar OSV.dev")
class OSVReal(unittest.TestCase):
    def test_mcp_remote_cve_2025_6514(self):
        """mcp-remote 0.1.15 tiene la inyección de comandos CVE-2025-6514, corregida en 0.1.16."""
        vulns = osv.check([Package("mcp-remote", "npm", "0.1.15")])
        found = {v.cve: v for v in vulns}
        self.assertIn("CVE-2025-6514", found)
        self.assertIn("0.1.16", found["CVE-2025-6514"].fixed)
        self.assertNotEqual(found["CVE-2025-6514"].severity, "desconocida")

    def test_version_corregida_sin_ese_cve(self):
        vulns = osv.check([Package("mcp-remote", "npm", "0.1.16")])
        self.assertNotIn("CVE-2025-6514", {v.cve for v in vulns})


if __name__ == "__main__":
    unittest.main()
