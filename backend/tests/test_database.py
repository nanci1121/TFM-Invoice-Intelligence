
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Assume running from root, so 'backend' is available
from backend.database import get_db, init_db, Base

class TestDatabaseInit:
    """Tests para la inicialización de base de datos"""
    
    @patch('backend.database.engine')
    def test_init_db_creates_tables(self, mock_engine):
        """Prueba que init_db llama a create_all"""
        # Mock metadata
        mock_metadata = MagicMock()
        with patch.object(Base, 'metadata', mock_metadata):
            init_db()
            mock_metadata.create_all.assert_called_once_with(bind=mock_engine)

class TestDatabaseSession:
    """Tests para la sesión de base de datos"""

    @patch('backend.database.SessionLocal')
    def test_get_db_session(self, mock_session_cls):
        """Prueba que get_db entrega y cierra la sesión"""
        mock_session = Mock()
        mock_session_cls.return_value = mock_session
        
        # Test generator
        gen = get_db()
        db = next(gen)
        
        assert db == mock_session
        
        # Test close on finally
        try:
            next(gen)
        except StopIteration:
            pass
            
        mock_session.close.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
