
import os
import sys
from pathlib import Path

# Add backend to path to import ai_service
# sys.path.append(os.path.join(os.getcwd(), 'backend')) # REMOVED: Rely on PYTHONPATH=.

# Mock requirements for import
import unittest
from unittest.mock import MagicMock, patch

# Now import the module to test
from backend import ai_service

class TestAgentConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Mock dependencies that are not needed for rule loading
        cls.patches = [
            patch('backend.ai_service.genai'),
            patch('backend.ai_service.OpenAI'),
            patch('backend.ai_service.requests'),
            patch('backend.ai_service.pytesseract'),
            patch('backend.ai_service.pdfplumber'),
            patch('backend.ai_service.Provider'),
            patch('backend.ai_service.ExtractionLog')
        ]
        for p in cls.patches:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()

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
