# Invoice Audit Agent

## Descripción General
Este proyecto es un **Agente Financiero Inteligente** diseñado para contables y auditores. Automatiza el procesamiento de facturas utilizando **IA Local (Ollama)** bajo un estricto conjunto de reglas de negocio definibles.

No solo extrae datos, sino que actúa como un analista experto que:
- Valida facturas contablemente.
- Genera KPIs ejecutivos automáticamente.
- Detecta anomalías y prepara informes de auditoría.

## Stack Tecnológico
- **Frontend**: HTML5, CSS3 (Glassmorphism), Chart.js.
- **Backend**: FastAPI (Python 3.11).
- **IA**: Ollama (Modelo qwen2.5:3b).
- **Agentic Core**: Reglas y Workflows definidos en Markdown (`.agent/`).
- **Base de Datos**: PostgreSQL.
- **Contenedores**: Docker & Docker Compose.

## Funcionalidades Agenticas
El sistema sigue reglas estrictas definidas en la carpeta `.agent`:
- **Reglas de Comportamiento**: Define la personalidad (Analista Financiero), lenguaje y límites (No inventar datos).
- **Workflows**:
    - `kpis-direccion`: Generación de reportes ejecutivos.
    - `validar-factura`: Detección de errores de forma.
    - `alertas`: Detección de anomalías en consumo/precio.

## Instalación y Ejecución

1. **Prerrequisitos**:
   - Docker y Docker Compose instalados.

2. **Configuración de variables de entorno**:
   ```bash
   # Copiar el archivo de ejemplo
   cp .env.example .env
   
   # Editar .env y cambiar las credenciales
   nano .env
   ```
   
   **Importante**: Cambia las credenciales por defecto en `.env`:
   - `POSTGRES_PASSWORD`: Usa una contraseña segura
   - `POSTGRES_USER`: Cambia el usuario si lo deseas

3. **Levantar infraestructura**:
   ```bash
   docker-compose up -d --build
   ```

4. **Acceso**:
   - Dashboard: `http://localhost:8000/frontend/index.html`
   - API Docs: `http://localhost:8000/docs`

## Estructura del Proyecto
- `.agent/`: **Cerebro del agente**. Contiene las reglas y workflows en Markdown.
- `backend/`: Lógica de API y conexión con Ollama.
- `frontend/`: Interfaz de usuario moderna.
- `docker-compose.yml`: Orquestación de servicios.

## Estado del Proyecto
✅ **Integración Completa**: El backend carga dinámicamente las reglas del agente.
✅ **Privacidad**: Todo el procesamiento es local.
✅ **Validado**: Tests de integración para asegurar la carga de reglas.
