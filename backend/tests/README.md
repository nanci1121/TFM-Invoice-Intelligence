# Tests del Proyecto Invoice Intelligence

## 📊 Resumen de Tests

✅ **15/15 tests pasando** (100% de éxito)

## 🧪 Suites de Tests

### 1. `TestExtractInvoiceData` (6 tests)
Prueba la extracción de datos de facturas con regex y AI:

- ✅ `test_extract_invoice_number_o2_pattern` - Detecta números de factura O2 (OM7VMJI018****)
- ✅ `test_extract_date_spanish_format` - Extrae fechas en español (15 de Marzo de 2025)
- ✅ `test_extract_category_telecom` - Identifica categoría Telecom por palabras clave
- ✅ `test_extract_category_electricity` - Identifica categoría Electricity
- ✅ `test_extract_handles_api_error` - Maneja errores de API gracefully
- ✅ `test_extract_all_months` - Procesa todos los meses en español correctamente

### 2. `TestValidateInvoice` (2 tests)
Prueba el workflow de validación de facturas:

- ✅ `test_validate_invoice_basic` - Validación básica de factura
- ✅ `test_validate_invoice_with_context` - Validación con contexto histórico

### 3. `TestGenerateKPIs` (3 tests)
Prueba la generación de KPIs para dirección:

- ✅ `test_generate_kpis_direccion_empty_invoices` - Maneja lista vacía correctamente
- ✅ `test_generate_kpis_direccion_single_invoice` - Procesa una factura
- ✅ `test_generate_kpis_direccion_multiple_categories` - Procesa múltiples categorías

### 4. `TestRegexPatterns` (2 tests)
Prueba los patrones regex de extracción:

- ✅ `test_o2_invoice_pattern` - Patrón OM[0-9A-Z]{7}[0-9A-Z\*]{3,}
- ✅ `test_date_spanish_pattern` - Patrón dd de Mes de yyyy

### 5. `TestCategoryDetection` (2 tests)
Prueba la detección de categorías por palabras clave:

- ✅ `test_detect_telecom_keywords` - Detecta: fibra, móvil, internet, O2, Movistar, etc.
- ✅ `test_detect_electricity_keywords` - Detecta: electricidad, luz, kWh, Iberdrola, etc.

## 🚀 Ejecución de Tests

### Ejecutar todos los tests
```bash
cd /home/venancio/Documentos/ProjectoFinalBIGschool
source venv/bin/activate
python -m pytest backend/tests/test_ai_service.py -v
```

### Ejecutar tests con cobertura
```bash
python -m pytest backend/tests/test_ai_service.py --cov=backend/ai_service --cov-report=html
```

### Ejecutar un test específico
```bash
python -m pytest backend/tests/test_ai_service.py::TestExtractInvoiceData::test_extract_invoice_number_o2_pattern -v
```

### Ejecutar una suite completa
```bash
python -m pytest backend/tests/test_ai_service.py::TestRegexPatterns -v
```

## 📝 Casos de Prueba Clave

### Extracción de Número de Factura O2
```python
# Patrón: OM[0-9A-Z]{7}[0-9A-Z\*]{3,}
Casos válidos:
- OM7VMJI018****  ✓
- OMABCD1234567   ✓
- OM1234567ABC    ✓

Casos inválidos:
- OM123           ✗ (muy corto)
- PM7VMJI018      ✗ (no empieza con OM)
```

### Extracción de Fechas en Español
```python
# Patrón: (\d{1,2})\s+de\s+(Mes)\s+de\s+(\d{4})
Casos válidos:
- "07 de Octubre de 2025"     → 2025-10-07 ✓
- "1 de Enero de 2024"         → 2024-01-01 ✓
- "31 de Diciembre de 2025"    → 2025-12-31 ✓

Casos inválidos:
- "15 October 2025"            ✗ (inglés)
- "Enero 15, 2025"             ✗ (formato americano)
```

### Detección de Categorías
```python
# Telecom
Palabras clave: fibra, móvil, movil, internet, telefon, o2, movistar, vodafone, orange

# Electricity  
Palabras clave: electricidad, luz, kwh, iberdrola, endesa, naturgy

# Gas
Palabras clave: gas, gas natural

# Water
Palabras clave: agua
```

## 🎯 Estrategia de Testing

### Hybrid Testing Approach
Los tests combinan:

1. **Regex Pre-processing**: Tests unitarios de patrones regex
2. **AI Extraction**: Mocks de Ollama API para pruebas aisladas
3. **Post-processing**: Validación de forzado de valores detectados por regex

### Mocking Strategy
```python
# Mockear la respuesta de Ollama
with patch('ai_service.requests.post') as mock_post:
    mock_post.return_value.json.return_value = {
        "response": json.dumps(mock_response)
    }
    mock_post.return_value.raise_for_status = Mock()
    
    result = extract_invoice_data(text)
```

## 📦 Dependencias de Testing

```txt
pytest==9.0.2
pytest-cov==7.0.0
httpx==0.28.1
```

## 🔧 Configuración (pytest.ini)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers --disable-warnings
```

## 🐛 Debugging Tests

### Ver traceback completo
```bash
python -m pytest -vv --tb=long
```

### Ejecutar con logs detallados
```bash
python -m pytest -v -s
```

### Ver solo tests fallidos
```bash
python -m pytest --lf
```

## 📈 Roadmap de Tests

### ✅ Completado
- Tests de extracción de datos (regex + AI)
- Tests de validación de facturas
- Tests de generación de KPIs
- Tests de patrones regex
- Tests de detección de categorías

### 🔄 En Progreso
- Tests de API endpoints (necesita ajuste de imports)
- Tests de base de datos (necesita configuración)

### 📅 Planificado
- Tests de integración end-to-end
- Tests de workflows completos
- Tests de carga y rendimiento
- Tests de interfaz (frontend)

## 💡 Mejores Prácticas

1. **Arrange-Act-Assert**: Estructura clara de tests
2. **Descriptive Names**: Nombres de tests auto-explicativos
3. **One Concept Per Test**: Un concepto por test
4. **Fast Tests**: Tests unitarios rápidos (< 1s)
5. **Independent Tests**: Sin dependencias entre tests
6. **Mock External Services**: Aislar servicios externos (Ollama, DB)

## 🏆 Métricas de Calidad

- **Success Rate**: 100% (15/15 tests passing)
- **Execution Time**: ~0.42s para suite completa
- **Code Coverage**: (Pendiente de configurar correctamente)
- **Maintainability**: Alta (tests bien estructurados y documentados)

---

**Última actualización**: 25 de Enero de 2026  
**Versión**: 1.0.0  
**Autor**: Venancio - TFM BIG School
