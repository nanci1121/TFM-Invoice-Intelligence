import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from backend.ai_service import _configure_clients, call_ai_service
from backend.database import SystemSetting

class TestAIConfig:
    """Tests para la configuración dinámica de proveedores de IA"""

    @patch('backend.ai_service.os.getenv')
    def test_configure_clients_default_env(self, mock_getenv):
        """Verifica que se usen valores de env por defecto si no hay DB"""
        mock_getenv.side_effect = lambda k, d=None: {
            "AI_PROVIDER": "ollama",
            "GEMINI_API_KEY": "env_gemini_key",
            "OPENAI_API_KEY": "env_openai_key"
        }.get(k, d)

        # Sin pasar DB
        _configure_clients(None)
        
        from backend import ai_service
        assert ai_service.AI_PROVIDER == "ollama"
        assert ai_service.GEMINI_API_KEY == "env_gemini_key"
        assert ai_service.OPENAI_API_KEY == "env_openai_key"

    def test_configure_clients_db_priority(self):
        """Verifica que la configuración de la DB tenga prioridad sobre Env"""
        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = [
            SystemSetting(key="AI_PROVIDER", value="gemini"),
            SystemSetting(key="GEMINI_API_KEY", value="db_gemini_key")
        ]

        with patch('backend.ai_service.os.getenv', return_value="ollama"):
            _configure_clients(mock_db)
            
            from backend import ai_service
            assert ai_service.AI_PROVIDER == "gemini"
            assert ai_service.GEMINI_API_KEY == "db_gemini_key"

    @patch('backend.ai_service.genai.GenerativeModel')
    def test_call_ai_service_gemini(self, mock_model_class):
        """Verifica que se llame a Gemini cuando está configurado"""
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = '{"result": "gemini_ok"}'
        mock_model_class.return_value = mock_model

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = [
            SystemSetting(key="AI_PROVIDER", value="gemini"),
            SystemSetting(key="GEMINI_API_KEY", value="valid_key")
        ]

        result = call_ai_service("test prompt", json_format=True, db=mock_db)
        
        assert "gemini_ok" in result
        mock_model.generate_content.assert_called_once()

    @patch('backend.ai_service.OpenAI')
    def test_call_ai_service_openai(self, mock_openai_class):
        """Verifica que se llame a OpenAI cuando está configurado"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = '{"result": "openai_ok"}'
        mock_openai_class.return_value = mock_client

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = [
            SystemSetting(key="AI_PROVIDER", value="openai"),
            SystemSetting(key="OPENAI_API_KEY", value="valid_key")
        ]

        result = call_ai_service("test prompt", json_format=True, db=mock_db)
        
        assert "openai_ok" in result
        mock_client.chat.completions.create.assert_called_once()

    @patch('backend.ai_service.requests.post')
    def test_call_ai_service_ollama_fallback(self, mock_post):
        """Verifica el fallback a Ollama si el proveedor no es válido o es ollama"""
        mock_post.return_value.json.return_value = {"response": "ollama_ok"}
        mock_post.return_value.raise_for_status = Mock()

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = [
            SystemSetting(key="AI_PROVIDER", value="ollama")
        ]

        result = call_ai_service("test prompt", db=mock_db)
        
        assert "ollama_ok" in result
        mock_post.assert_called_once()
