# Tests del Proyecto Invoice Intelligence

## 📊 Resumen de Tests

✅ **40/40 tests pasando** (100% de éxito)

## 🧪 Suites de Tests

### 1. `TestAIConfig` (New!)
Prueba la configuración dinámica de proveedores de IA:
- ✅ `test_configure_clients_default_env` - Verifica uso de variables de entorno.
- ✅ `test_configure_clients_db_priority` - Asegura que la DB tiene prioridad sobre env.
- ✅ `test_call_ai_service_gemini` - Mock de integración con Google Gemini.
- ✅ `test_call_ai_service_openai` - Mock de integración con OpenAI.
- ✅ `test_call_ai_service_ollama_fallback` - Fallback seguro a Ollama local.

### 2. `TestExtractInvoiceData` (6 tests)
Prueba la extracción de datos de facturas con regex y AI:
- ✅ `test_extract_invoice_number_o2_pattern` - Detecta números de factura O2.
- ✅ `test_extract_date_spanish_format` - Extrae fechas en español.
- ✅ `test_extract_category_telecom` - Identifica categoría Telecom.
- ✅ `test_extract_category_electricity` - Identifica categoría Electricity.
- ✅ `test_extract_handles_api_error` - Maneja errores de API gracefully.
- ✅ `test_extract_all_months` - Procesa todos los meses en español correctamente.

### 3. `TestAPI` (Endpoints)
Verifica los endpoints de la API FastAPI:
- ✅ `test_health_check` - Health signal.
- ✅ `test_reports_with_data` - Listado de facturas.
- ✅ `test_upload_pdf_success` - Workflow de subida completo.
- ✅ `test_get_settings_default` - Lectura de configuración de IA.
- ✅ `test_post_settings_persistence` - Escritura y persistencia de API Keys.

### 4. `TestAgentConfig` (Integration)
Verifica la carga de reglas del agente `.agent`:
- ✅ `test_load_core_rules` - Carga de reglas fundamentales.
- ✅ `test_workflow_instructions_loading` - Carga de instrucciones de workflows.

### 5. `TestDatabase`
- ✅ `test_init_db_creates_tables` - Inicialización de esquema.
- ✅ `test_get_db_session` - Gestión de sesiones SQLAlchemy.

## 🚀 Ejecución de Tests

Asegúrate de tener el entorno virtual activo.

### Ejecutar todos los tests
```bash
export TESTING=true
export PYTHONPATH=.
python -m pytest backend/tests/ -v
```

### Ejecutar con Docker (Recomendado)
```bash
docker exec tfm_invoice_app pytest backend/tests/ -v
```

### Reporte de Cobertura
```bash
python -m pytest backend/tests/ --cov=backend --cov-report=term-missing
```

## 🎯 Estrategia de Testing

- **Aislamiento**: Se utiliza SQLite en memoria o archivos (`test.db`) para no ensuciar la DB de producción.
- **Mocks Controlados**: Uso de `unittest.mock.patch` para evitar llamadas reales a APIs externas durante los tests.
- **Detección Híbrida**: Se valida que los patrones Regex tengan prioridad sobre las sugerencias de la IA.

## 📈 Roadmap de Tests

### ✅ Completado
- Tests de extracción de datos y patrones Regex.
- Tests de configuración dinámica de IA (Gemini/OpenAI/Ollama).
- Tests de API endpoints y persistencia de settings.
- Tests de integración de reglas del agente.
- Inicialización y gestión de Base de Datos.

### 📅 Planificado
- Tests de integración end-to-end con archivos reales.
- Tests de estrés para el watcher de carpetas.
- Verificación visual del frontend (Playwright/Selenium).

---

**Última actualización**: 29 de Enero de 2026  
**Versión**: 1.1.0  
**Autor**: Venancio - TFM BIG School
