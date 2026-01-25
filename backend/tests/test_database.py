
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Assume running from root, so 'backend' is available
from backend.database import get_db, init_db, Base

class TestDatabaseInit:
    """Tests para la inicialización de base de datos"""
    
    def test_init_db_creates_tables(self):
        """Prueba que init_db crea las tablas correctamente"""
        # The fixture already calls init_db, so we just verify tables exist
        from backend.database import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Verify key tables were created
        assert 'invoices' in tables
        assert 'providers' in tables
        assert 'extraction_logs' in tables

class TestDatabaseSession:
    """Tests para la sesión de base de datos"""

    def test_get_db_session(self):
        """Prueba que get_db entrega y cierra la sesión"""
        from backend.database import get_db
        
        # Test generator
        gen = get_db()
        db = next(gen)
        
        # Verify we got a session
        assert db is not None
        assert hasattr(db, 'query')
        assert hasattr(db, 'close')
        
        # Test close on finally
        try:
            next(gen)
        except StopIteration:
            pass

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
