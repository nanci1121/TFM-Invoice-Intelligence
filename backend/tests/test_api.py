
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json
import os
from io import BytesIO

# Import directly from the backend package
from backend.main import app

client = TestClient(app)

class TestHealthEndpoint:
    """Tests para el endpoint de health check"""
    
    def test_health_check(self):
        """Prueba que el endpoint de health responde correctamente"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestReportsEndpoint:
    """Tests para el endpoint de reportes"""
    
    @patch('backend.main.get_db')
    def test_reports_empty_database(self, mock_db):
        """Prueba reportes con base de datos vacía"""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db.return_value.__enter__.return_value = mock_connection
        
        response = client.get("/reports")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    @patch('backend.main.get_db')
    def test_reports_with_data(self, mock_db):
        """Prueba reportes con datos"""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, "INV001", "2025-01-15", "O2", 45.50, "EUR", "Purchase", 
             "Telecom", 100.0, "GB", "invoice.pdf")
        ]
        mock_cursor.description = [
            ("id",), ("invoice_number",), ("date",), ("vendor_name",),
            ("total_amount",), ("currency",), ("type",), ("category",),
            ("consumption",), ("consumption_unit",), ("file_path",)
        ]
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db.return_value.__enter__.return_value = mock_connection
        
        response = client.get("/reports")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["invoice_number"] == "INV001"
        assert data[0]["vendor_name"] == "O2"


class TestAdvancedStatsEndpoint:
    """Tests para el endpoint de estadísticas avanzadas"""
    
    @patch('backend.main.get_db')
    def test_advanced_stats_empty(self, mock_db):
        """Prueba estadísticas con datos vacíos"""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db.return_value.__enter__.return_value = mock_connection
        
        response = client.get("/advanced-stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_invoices"] == 0
        assert data["total_spent"] == 0


class TestWorkflowEndpoints:
    """Tests para los endpoints de workflows"""
    
    @patch('backend.main.validate_invoice')
    def test_workflow_validar_factura(self, mock_validate):
        """Prueba el workflow de validación"""
        mock_validate.return_value = json.dumps({
            "validacion": "OK",
            "errores_detectados": []
        })
        
        response = client.post("/workflow/validar-factura", json={
            "invoice_data": {
                "invoice_number": "TEST123",
                "total_amount": 100
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "validacion" in data
    
    @patch('backend.main.generate_kpis_direccion')
    def test_workflow_kpis_direccion(self, mock_kpis):
        """Prueba el workflow de KPIs para dirección"""
        mock_kpis.return_value = json.dumps({
            "gasto_total": 500,
            "gasto_por_categoria": {"Telecom": 200, "Electricity": 300}
        })
        
        response = client.post("/workflow/kpis-direccion", json={
            "invoices": [
                {"category": "Telecom", "total_amount": 200},
                {"category": "Electricity", "total_amount": 300}
            ]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "gasto_total" in data or "kpis" in data
    
    @patch('backend.main.generate_kpis_reclamacion')
    def test_workflow_kpis_reclamacion(self, mock_kpis):
        """Prueba el workflow de KPIs para reclamación"""
        mock_kpis.return_value = json.dumps({
            "base_reclamacion": "Cobro incorrecto",
            "evidencias": ["Diferencia de 20 EUR"]
        })
        
        response = client.post("/workflow/kpis-reclamacion", json={
            "invoice_data": {"invoice_number": "TEST123"},
            "historical_data": []
        })
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
    
    @patch('backend.main.compare_supplier')
    def test_workflow_comparar_proveedor(self, mock_compare):
        """Prueba el workflow de comparación de proveedor"""
        mock_compare.return_value = json.dumps({
            "proveedor_actual": "O2",
            "ahorro_potencial": 10.5
        })
        
        response = client.post("/workflow/comparar-proveedor", json={
            "current_invoice": {"vendor_name": "O2", "total_amount": 50},
            "market_data": {"promedio_mercado": 40}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
    
    @patch('backend.main.generate_meeting_summary')
    def test_workflow_resumen_reunion(self, mock_summary):
        """Prueba el workflow de resumen para reunión"""
        mock_summary.return_value = json.dumps({
            "resumen_ejecutivo": "Gasto total: 500 EUR",
            "principales_conclusiones": ["Aumento del 10%"]
        })
        
        response = client.post("/workflow/resumen-reunion", json={
            "period": "Q1 2025",
            "invoices": []
        })
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
    
    @patch('backend.main.check_alerts')
    def test_workflow_alertas(self, mock_alerts):
        """Prueba el workflow de alertas"""
        mock_alerts.return_value = json.dumps({
            "alertas": [
                {"tipo": "ANOMALIA", "descripcion": "Consumo inusual"}
            ]
        })
        
        response = client.post("/workflow/alertas", json={
            "invoices": [{"total_amount": 200}],
            "thresholds": {"max_amount": 150}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "alertas" in data or isinstance(data, dict)


class TestUploadEndpoint:
    """Tests para el endpoint de carga de archivos"""
    
    @patch('backend.main.extract_invoice_data')
    @patch('backend.main.get_db')
    @patch('backend.main.os.path.exists')
    def test_upload_pdf_success(self, mock_exists, mock_db, mock_extract):
        """Prueba carga exitosa de PDF"""
        mock_exists.return_value = False  # No existe duplicado
        
        mock_extract.return_value = json.dumps({
            "invoice_number": "TEST123",
            "date": "2025-01-15",
            "vendor_name": "O2",
            "total_amount": 45.50,
            "currency": "EUR",
            "type": "Purchase",
            "category": "Telecom",
            "consumption": 100,
            "consumption_unit": "GB"
        })
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # No duplicado en DB
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db.return_value.__enter__.return_value = mock_connection
        
        # Crear un archivo de prueba
        file_content = b"PDF content"
        files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}
        
        with patch('backend.main.get_text_from_pdf', return_value="Factura de prueba"):
            response = client.post("/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_upload_no_file(self):
        """Prueba carga sin archivo"""
        response = client.post("/upload")
        assert response.status_code == 422  # Validation error


class TestDeleteEndpoint:
    """Tests para el endpoint de eliminación"""
    
    @patch('backend.main.get_db')
    @patch('backend.main.os.remove')
    @patch('backend.main.os.path.exists')
    def test_delete_invoice_success(self, mock_exists, mock_remove, mock_db):
        """Prueba eliminación exitosa de factura"""
        mock_exists.return_value = True
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ("backend/uploads/test.pdf",)
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db.return_value.__enter__.return_value = mock_connection
        
        response = client.delete("/delete/1")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    @patch('backend.main.get_db')
    def test_delete_invoice_not_found(self, mock_db):
        """Prueba eliminación de factura inexistente"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db.return_value.__enter__.return_value = mock_connection
        
        response = client.delete("/delete/999")
        assert response.status_code == 404


class TestChatEndpoint:
    """Tests para el endpoint de chat"""
    
    @patch('backend.main.chat_with_invoices')
    def test_chat_basic_query(self, mock_chat):
        """Prueba consulta básica al chat"""
        mock_chat.return_value = "La factura más alta es de 150 EUR"
        
        response = client.post("/chat", json={
            "query": "¿Cuál es la factura más alta?"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
    
    def test_chat_empty_query(self):
        """Prueba chat con consulta vacía"""
        response = client.post("/chat", json={
            "query": ""
        })
        
        assert response.status_code in [200, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
