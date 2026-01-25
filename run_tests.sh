#!/bin/bash

# Script para ejecutar los tests del proyecto

echo "🧪 Ejecutando tests del proyecto..."
echo ""

# Ir al directorio backend
cd "$(dirname "$0")/backend"

# Instalar dependencias si no están
if ! python3 -c "import pytest" 2>/dev/null; then
    echo "📦 Instalando pytest..."
    pip install pytest pytest-cov httpx
fi

# Ejecutar todos los tests
echo "📋 Ejecutando todos los tests..."
python3 -m pytest tests/ -v

# Generar reporte de cobertura
echo ""
echo "📊 Generando reporte de cobertura..."
python3 -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html

echo ""
echo "✅ Tests completados. Reporte de cobertura en backend/htmlcov/index.html"
