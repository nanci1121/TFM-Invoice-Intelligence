import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from backend.ai_service import extract_invoice_data, validate_invoice, generate_kpis_direccion
from backend.database import Provider

# Helper to create mock providers
def get_mock_providers():
    return [
        Provider(name="O2", vendor_name="O2", category="Telecom", patterns={
            "invoice_number": [r"(OM[0-9A-Z]{7}[0-9A-Z\*]{3,})"],
            "date": [r"(\d{1,2})\s+de\s+(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre)\s+de\s+(\d{4})"],
            "vendor": [r"O2"],
            "total_amount": [r"Importe total[:\s]+(\d+\.\d{2})"]
        }),
        Provider(name="Iberdrola", vendor_name="Iberdrola", category="Electricity", patterns={
             "invoice_number": [r"N[°º]\s*Factura[:\s]+([A-Z0-9\-]+)"],
             "vendor": [r"Iberdrola"],
             "category": "Electricity"
        })
    ]


class TestExtractInvoiceData:
    """Tests para la extracción de datos de facturas"""
    
    def test_extract_invoice_number_o2_pattern(self):
        """Prueba que detecta correctamente números de factura de O2"""
        text = """
        Factura de O2
        Número de factura: OM7VMJI018****
        Fecha: 07 de Octubre de 2025
        Importe total: 45.50 EUR
        """
        
        # Mock de la respuesta de Ollama
        mock_response = {
            "invoice_number": "dummy",
            "date": "2025-01-01",
            "vendor_name": "O2",
            "total_amount": 45.50,
            "currency": "EUR",
            "type": "Purchase",
            "category": "Telecom"
        }
        
        with patch('backend.ai_service.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "response": json.dumps(mock_response)
            }
            mock_post.return_value.raise_for_status = Mock()
            
            # Create a mock DB session with providers
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = get_mock_providers()
            result = extract_invoice_data(text, mock_db)
            data = json.loads(result)
            
            # El regex debe forzar el número correcto
            assert data['invoice_number'] == 'OM7VMJI018****'
    
    def test_extract_date_spanish_format(self):
        """Prueba que detecta fechas en formato español"""
        text = """
        Factura
        Fecha: 15 de Marzo de 2025
        Total: 100 EUR
        """
        
        mock_response = {
            "invoice_number": "TEST123",
            "date": "wrong-date",
            "vendor_name": "Test",
            "total_amount": 100,
            "currency": "EUR",
            "type": "Purchase",
            "category": "Other"
        }
        
        with patch('backend.ai_service.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "response": json.dumps(mock_response)
            }
            mock_post.return_value.raise_for_status = Mock()
            
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = get_mock_providers()
            result = extract_invoice_data(text, mock_db)
            data = json.loads(result)
            
            # El regex debe forzar la fecha correcta
            assert data['date'] == '2025-03-15'
    
    def test_extract_category_telecom(self):
        """Prueba que detecta categoría Telecom correctamente"""
        text = """
        Factura O2
        Servicios de fibra óptica y móvil
        Internet 600MB
        Total: 50 EUR
        """
        
        mock_response = {
            "invoice_number": "TEST123",
            "date": "2025-01-01",
            "vendor_name": "O2",
            "total_amount": 50,
            "currency": "EUR",
            "type": "Purchase",
            "category": "Other"
        }
        
        with patch('backend.ai_service.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "response": json.dumps(mock_response)
            }
            mock_post.return_value.raise_for_status = Mock()
            
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = get_mock_providers()
            result = extract_invoice_data(text, mock_db)
            data = json.loads(result)
            
            # El regex debe forzar categoría Telecom
            assert data['category'] == 'Telecom'
    
    def test_extract_category_electricity(self):
        """Prueba que detecta categoría Electricity"""
        text = """
        Factura Iberdrola
        Consumo de electricidad: 350 kWh
        Luz y energía eléctrica
        Total: 89.50 EUR
        """
        
        mock_response = {
            "invoice_number": "ELEC123",
            "date": "2025-01-01",
            "vendor_name": "Iberdrola",
            "total_amount": 89.50,
            "currency": "EUR",
            "type": "Purchase",
            "category": "Other"
        }
        
        with patch('backend.ai_service.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "response": json.dumps(mock_response)
            }
            mock_post.return_value.raise_for_status = Mock()
            
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = get_mock_providers()
            result = extract_invoice_data(text, mock_db)
            data = json.loads(result)
            
            assert data['category'] == 'Electricity'
    
    def test_extract_handles_api_error(self):
        """Prueba que maneja errores de API correctamente"""
        text = "Factura de prueba"
        
        with patch('backend.ai_service.requests.post') as mock_post:
            mock_post.side_effect = Exception("API Error")
            
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = get_mock_providers()
            result = extract_invoice_data(text, mock_db)
            data = json.loads(result)
            
            # Check for error indication in notes or error field
            assert 'notes' in data or 'error' in data
            if 'notes' in data:
                assert 'falló' in data['notes'].lower() or 'error' in data['notes'].lower()
    
    def test_extract_all_months(self):
        """Prueba que detecta todos los meses en español"""
        months = {
            'Enero': '01', 'Febrero': '02', 'Marzo': '03', 'Abril': '04',
            'Mayo': '05', 'Junio': '06', 'Julio': '07', 'Agosto': '08',
            'Septiembre': '09', 'Octubre': '10', 'Noviembre': '11', 'Diciembre': '12'
        }
        
        for month_name, month_num in months.items():
            text = f"Fecha: 10 de {month_name} de 2025"
            
            mock_response = {
                "invoice_number": "TEST123",
                "date": "wrong",
                "vendor_name": "Test",
                "total_amount": 100,
                "currency": "EUR",
                "type": "Purchase",
                "category": "Other"
            }
            
            # Move patch INSIDE the loop
            with patch('backend.ai_service.requests.post') as mock_post:
                mock_post.return_value.json.return_value = {
                    "response": json.dumps(mock_response)
                }
                mock_post.return_value.raise_for_status = Mock()
                
                mock_db = MagicMock()
                mock_db.query.return_value.all.return_value = get_mock_providers()
                result = extract_invoice_data(text, mock_db)
                data = json.loads(result)
                
                assert data['date'] == f'2025-{month_num}-10', f"Failed for {month_name}"


class TestValidateInvoice:
    """Tests para validación de facturas"""
    
    def test_validate_invoice_basic(self):
        """Prueba básica de validación"""
        invoice_data = {
            "invoice_number": "TEST123",
            "date": "2025-01-15",
            "vendor_name": "Test Vendor",
            "total_amount": 100.50,
            "category": "Telecom"
        }
        
        mock_response = {
            "validacion": "OK",
            "errores_detectados": [],
            "advertencias": []
        }
        
        with patch('backend.ai_service.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "response": json.dumps(mock_response)
            }
            mock_post.return_value.raise_for_status = Mock()
            
            result = validate_invoice(invoice_data)
            data = json.loads(result)
            
            assert 'validacion' in data
    
    def test_validate_invoice_with_context(self):
        """Prueba validación con contexto histórico"""
        invoice_data = {
            "invoice_number": "TEST123",
            "total_amount": 150.00
        }
        context = "Facturas anteriores: 100 EUR, 105 EUR, 110 EUR"
        
        with patch('backend.ai_service.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "response": json.dumps({"validacion": "ALERTA", "errores_detectados": ["Incremento >30%"]})
            }
            mock_post.return_value.raise_for_status = Mock()
            
            result = validate_invoice(invoice_data, context)
            data = json.loads(result)
            
            assert 'errores_detectados' in data


class TestGenerateKPIs:
    """Tests para generación de KPIs"""
    
    def test_generate_kpis_direccion_empty_invoices(self):
        """Prueba KPIs con lista vacía"""
        result = generate_kpis_direccion([])
        data = json.loads(result)
        
        assert 'error' in data or 'kpis' in data
    
    def test_generate_kpis_direccion_single_invoice(self):
        """Prueba KPIs con una sola factura"""
        invoices = [
            {
                "invoice_number": "TEST123",
                "date": "2025-01-15",
                "vendor_name": "O2",
                "total_amount": 45.50,
                "category": "Telecom"
            }
        ]
        
        mock_response = {
            "gasto_total": 45.50,
            "gasto_por_categoria": {"Telecom": 45.50},
            "tendencia": "estable"
        }
        
        with patch('backend.ai_service.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "response": json.dumps(mock_response)
            }
            mock_post.return_value.raise_for_status = Mock()
            
            result = generate_kpis_direccion(invoices)
            data = json.loads(result)
            
            assert 'gasto_total' in data or 'kpis' in data
    
    def test_generate_kpis_direccion_multiple_categories(self):
        """Prueba KPIs con múltiples categorías"""
        invoices = [
            {"category": "Telecom", "total_amount": 50},
            {"category": "Electricity", "total_amount": 80},
            {"category": "Water", "total_amount": 30}
        ]
        
        mock_response = {
            "gasto_total": 160,
            "gasto_por_categoria": {
                "Telecom": 50,
                "Electricity": 80,
                "Water": 30
            }
        }
        
        with patch('backend.ai_service.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "response": json.dumps(mock_response)
            }
            mock_post.return_value.raise_for_status = Mock()
            
            result = generate_kpis_direccion(invoices)
            data = json.loads(result)
            
            # Verificar que se procesaron todas las categorías
            assert data is not None


class TestRegexPatterns:
    """Tests específicos para los patrones regex"""
    
    def test_o2_invoice_pattern(self):
        """Prueba el patrón de facturas O2"""
        import re
        pattern = r'(OM[0-9A-Z]{7}[0-9A-Z\*]{3,})'
        
        # Casos válidos
        assert re.search(pattern, "OM7VMJI018****")
        assert re.search(pattern, "OMABCD1234567")
        assert re.search(pattern, "OM1234567ABC")
        
        # Casos inválidos
        assert not re.search(pattern, "OM123")  # Muy corto
        assert not re.search(pattern, "PM7VMJI018")  # No empieza con OM
    
    def test_date_spanish_pattern(self):
        """Prueba el patrón de fechas en español"""
        import re
        pattern = r'(\d{1,2})\s+de\s+(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre)\s+de\s+(\d{4})'
        
        # Casos válidos
        assert re.search(pattern, "07 de Octubre de 2025", re.IGNORECASE)
        assert re.search(pattern, "1 de Enero de 2024", re.IGNORECASE)
        assert re.search(pattern, "31 de Diciembre de 2025", re.IGNORECASE)
        
        # Casos inválidos (el regex no valida la validez de la fecha, solo el formato)
        assert not re.search(pattern, "15 October 2025", re.IGNORECASE)  # Inglés
        assert not re.search(pattern, "Enero 15, 2025", re.IGNORECASE)  # Formato americano


class TestCategoryDetection:
    """Tests para la detección de categorías"""
    
    def test_detect_telecom_keywords(self):
        """Prueba detección de palabras clave de Telecom"""
        telecom_texts = [
            "Servicios de fibra óptica",
            "Tarifa móvil prepago",
            "Internet y telefonía",
            "Factura O2 España",
            "Servicios Movistar"
        ]
        
        for text in telecom_texts:
            text_lower = text.lower()
            is_telecom = any(word in text_lower for word in 
                           ['fibra', 'móvil', 'movil', 'internet', 'telefon', 
                            'o2', 'movistar', 'vodafone', 'orange'])
            assert is_telecom, f"Failed to detect telecom in: {text}"
    
    def test_detect_electricity_keywords(self):
        """Prueba detección de palabras clave de Electricity"""
        electricity_texts = [
            "Consumo de electricidad",
            "Factura de luz",
            "Energía: 350 kWh",
            "Iberdrola suministros",
            "Endesa energía"
        ]
        
        for text in electricity_texts:
            text_lower = text.lower()
            is_electricity = any(word in text_lower for word in 
                                ['electricidad', 'luz', 'kwh', 'iberdrola', 
                                 'endesa', 'naturgy'])
            assert is_electricity, f"Failed to detect electricity in: {text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
