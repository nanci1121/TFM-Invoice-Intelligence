import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection, init_db


class TestDatabaseConnection:
    """Tests para la conexión a base de datos"""
    
    @patch('database.psycopg2.connect')
    def test_get_db_connection_success(self, mock_connect):
        """Prueba conexión exitosa"""
        mock_connection = Mock()
        mock_connect.return_value = mock_connection
        
        with get_db_connection() as conn:
            assert conn == mock_connection
    
    @patch('database.psycopg2.connect')
    def test_get_db_connection_failure(self, mock_connect):
        """Prueba fallo de conexión"""
        mock_connect.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception):
            with get_db_connection() as conn:
                pass


class TestDatabaseInit:
    """Tests para la inicialización de base de datos"""
    
    @patch('database.get_db_connection')
    def test_init_db_creates_table(self, mock_db):
        """Prueba que init_db crea la tabla"""
        mock_cursor = Mock()
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db.return_value.__enter__.return_value = mock_connection
        
        init_db()
        
        # Verificar que se ejecutó CREATE TABLE
        assert mock_cursor.execute.called
        assert "CREATE TABLE IF NOT EXISTS" in mock_cursor.execute.call_args[0][0]
    
    @patch('database.get_db_connection')
    def test_init_db_handles_error(self, mock_db):
        """Prueba que init_db maneja errores"""
        mock_connection = Mock()
        mock_connection.cursor.side_effect = Exception("DB Error")
        mock_db.return_value.__enter__.return_value = mock_connection
        
        # No debería lanzar excepción
        try:
            init_db()
        except Exception:
            pytest.fail("init_db debería manejar errores gracefully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
