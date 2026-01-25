
import os
import sys
from pathlib import Path

# Add backend to path to import ai_service
# sys.path.append(os.path.join(os.getcwd(), 'backend')) # REMOVED: Rely on PYTHONPATH=.

# Mock requirements for import
import unittest
from unittest.mock import MagicMock, patch

# Mock database and requests to avoid external dependencies during config test
sys.modules['backend.database'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['pdfplumber'] = MagicMock()
sys.modules['pytesseract'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()

# Now import the module to test
from backend import ai_service

class TestAgentConfig(unittest.TestCase):
    def setUp(self):
        # Ensure we are in the root directory for relative paths to work
        self.root_dir = os.getcwd()
        if not self.root_dir.endswith('ProjectoFinalBIGschool'):
             print(f"Warning: Tests running from {self.root_dir}")

    def test_load_core_rules(self):
        """Verify that core rules are loaded from markdown files"""
        rules = ai_service.get_core_rules()
        print(f"\nLoaded Rules Length: {len(rules)}")
        self.assertIn("REGLAS DE COMPORTAMIENTO (CARGADAS DINÁMICAMENTE)", rules)
        self.assertIn("El agente actúa siempre como analista", rules) # From enfoque-del-dominio.md
        self.assertIn("No inventa datos", rules) # From no-invencion.md

    def test_workflow_instructions_loading(self):
        """Verify that workflow instruction files are readable"""
        workflows = [
            "workflows/extraer-factura.md",
            "workflows/validar-factura.md",
            "workflows/kpis-direccion.md", 
            "workflows/alertas.md"
        ]
        
        for wf in workflows:
            content = ai_service.load_agent_file(wf)
            self.assertTrue(len(content) > 0, f"Failed to load {wf}")
            print(f"Successfully loaded {wf} ({len(content)} chars)")

if __name__ == '__main__':
    unittest.main()
