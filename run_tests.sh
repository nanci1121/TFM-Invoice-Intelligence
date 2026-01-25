#!/bin/bash

# Script para ejecutar los tests del proyecto

echo "🧪 Ejecutando tests del proyecto..."
echo ""

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

# Establecer modo de testing
export TESTING=true

# Ir al directorio backend
cd "$(dirname "$0")/backend"

# Ejecutar todos los tests
echo "📋 Ejecutando todos los tests..."
python -m pytest tests/ -v

# Generar reporte de cobertura
echo ""
echo "📊 Generando reporte de cobertura..."
python -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html

echo ""
echo "✅ Tests completados. Reporte de cobertura en backend/htmlcov/index.html"
