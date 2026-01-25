#!/bin/bash

# Script rápido para ejecutar tests
cd "$(dirname "$0")"

echo "🧪 Ejecutando tests..."
source venv/bin/activate
python -m pytest backend/tests/test_ai_service.py -v --html=backend/tests/report.html --self-contained-html

echo ""
echo "✅ Tests completados!"
echo "📊 Ver reporte: file://$(pwd)/backend/tests/report.html"
