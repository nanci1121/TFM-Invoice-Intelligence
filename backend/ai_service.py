import requests
import json
import os
import pytesseract
from PIL import Image
import pdfplumber
import re
from datetime import datetime
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from .database import Provider, ExtractionLog, SystemSetting
import google.generativeai as genai
from openai import OpenAI

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434/api/generate")

# Inicialización básica de clientes (se reconfiguran en cada llamada si cambian las keys)
def _configure_clients(db: Session = None):
    """Configura los clientes de IA usando settings de DB o Env"""
    global AI_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY, openai_client

    # Valores por defecto de Env
    p = os.getenv("AI_PROVIDER", "ollama").lower()
    g_key = os.getenv("GEMINI_API_KEY")
    o_key = os.getenv("OPENAI_API_KEY")

    if db:
        settings = db.query(SystemSetting).all()
        s_dict = {s.key: s.value for s in settings}
        p = s_dict.get("AI_PROVIDER", p).lower()
        g_key = s_dict.get("GEMINI_API_KEY", g_key)
        o_key = s_dict.get("OPENAI_API_KEY", o_key)

    AI_PROVIDER = p
    GEMINI_API_KEY = g_key
    OPENAI_API_KEY = o_key

    if AI_PROVIDER == "gemini" and GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    
    if AI_PROVIDER == "openai" and OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    else:
        openai_client = None

def call_ai_service(prompt: str, json_format: bool = False, db: Session = None) -> str:
    """Función unificada para llamar al proveedor de IA configurado"""
    
    _configure_clients(db)
    
    if AI_PROVIDER == "gemini" and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            generation_config = {"response_mime_type": "application/json"} if json_format else {}
            response = model.generate_content(prompt, generation_config=generation_config)
            return response.text
        except Exception as e:
            logger.error(f"❌ Error Gemini: {e}")
            return str(e)

    elif AI_PROVIDER == "openai" and openai_client:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"} if json_format else None
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"❌ Error OpenAI: {e}")
            return str(e)
            
    else: # Default: Ollama
        payload = {
            "model": "qwen2.5:3b",
            "prompt": prompt,
            "stream": False
        }
        if json_format:
            payload["format"] = "json"
            
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=90)
            response.raise_for_status()
            result = response.json()
            return result.get('response', '')
        except Exception as e:
            logger.error(f"❌ Error Ollama: {e}")
            return str(e)

# Helper to read agent files
def load_agent_file(path: str) -> str:
    """Lee un archivo de reglas o workflow del directorio .agent"""
    # En Docker, .agent se monta en /app/.agent
    # En local, intentamos buscarlo relativo al proyecto
    
    # Priority 1: Docker path
    docker_path = Path("/app/.agent") / path
    if docker_path.exists():
        return docker_path.read_text(encoding="utf-8")
        
    # Priority 2: Local relative path (assuming running from root)
    local_path = Path(".agent") / path
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")
        
    # Priority 3: Parent relative (if running from backend/)
    parent_path = Path("../.agent") / path
    if parent_path.exists():
        return parent_path.read_text(encoding="utf-8")
        
    logger.warning(f"⚠️ No se encontró el archivo del agente: {path}")
    return ""

def get_core_rules() -> str:
    """Carga y concatena todas las reglas del agente"""
    rules_dir = "rules"
    rules_files = [
        "enfoque-del-dominio.md", 
        "no-invencion.md", 
        "prioridad-de-datos.md",
        "lenguaje-profesional.md",
        "estructura.md",
        "orientacion-a-decision.md",
        "suposiciones-explicitas.md"
    ]
    
    combined_rules = "REGLAS DE COMPORTAMIENTO (CARGADAS DINÁMICAMENTE):\n"
    for rf in rules_files:
        content = load_agent_file(f"{rules_dir}/{rf}")
        if content:
            combined_rules += f"{content}\n"
            
    if len(combined_rules) < 100:
        # Fallback si no se cargan
        logger.warning("⚠️ Usando reglas por defecto (frontend no montado o archivos perdidos)")
        return """
        REGLAS DE COMPORTAMIENTO:
        1. Actúas como analista contable-financiero specialized en facturas.
        2. Prioriza datos numéricos.
        3. Foco en control interno y ahorro.
        """
    return combined_rules

# REGLAS FUNDAMENTALES (aplicadas a todos los prompts)
CORE_RULES = get_core_rules()

def get_text_from_pdf(pdf_path: str):
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # extract_text en pdfplumber mantiene mejor el layout visual
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        return f"PDF Error: {str(e)}"

def get_text_from_image(image_path: str):
    try:
        return pytesseract.image_to_string(Image.open(image_path))
    except Exception as e:
        return f"OCR Error: {str(e)}"

def extract_invoice_data(text: str, db: Session, filename: str = "unknown"):
    """Workflow /extraer_factura - Extracción estandarizada con patrones en DB"""
    
    logger.info(f"🔍 Iniciando extracción de factura: {filename}...")
    
    extracted_hints = {}
    matched_provider = None
    best_score = -1
    best_partial = {}
    debug_scores = []

    # Obtener proveedores de la DB
    providers = db.query(Provider).all()
    
    # Buscar el mejor proveedor por puntuación
    for provider_config in providers:
        score = 0
        partial = {}
        matches_found = []

        patterns = provider_config.patterns

        # Vendor (peso alto)
        vendor_patterns = patterns.get('vendor', [])
        for vendor_pattern in vendor_patterns:
            # MEJORA: Evitar O2 (%) usando word boundaries si el patrón es O2 o similar
            working_pattern = vendor_pattern
            if working_pattern.lower() == "o2":
                working_pattern = r"\bO2\b"
            
            if re.search(working_pattern, text, re.IGNORECASE):
                partial['vendor_name'] = provider_config.vendor_name
                partial['category'] = provider_config.category
                score += 5 
                matches_found.append(f"vendor:{vendor_pattern}")
                break

        # NIF/CIF (Peso máximo si se encuentra)
        nif_patterns = patterns.get('nif', [])
        for nif_p in nif_patterns:
            if re.search(nif_p, text, re.IGNORECASE):
                score += 10
                matches_found.append(f"nif:{nif_p}")
                break

        # Número de factura
        for pattern in patterns.get('invoice_number', []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                partial['invoice_number'] = match.group(1)
                score += 2
                matches_found.append(f"invoice_number:{pattern}")
                break

        # Fecha
        for pattern in patterns.get('date', []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    if groups[1].isdigit():
                        day, month, year = groups
                        partial['date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        day, month_name, year = groups
                        month_map = {
                            'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                            'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                            'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                        }
                        month = month_map.get(month_name.lower(), '01')
                        partial['date'] = f"{year}-{month}-{day.zfill(2)}"
                score += 2
                matches_found.append(f"date:{pattern}")
                break

        # Importe total
        for pattern in patterns.get('total_amount', []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = match.group(1).replace(',', '.')
                try:
                    partial['total_amount'] = float(amount)
                    score += 1
                    matches_found.append(f"total_amount:{pattern}")
                except:
                    pass
                break

        debug_scores.append({
            "provider": provider_config.name,
            "score": score,
            "matches": matches_found
        })

        if score > best_score:
            best_score = score
            matched_provider = provider_config
            best_partial = partial

    # Aplicar el mejor resultado encontrado
    extracted_hints.update(best_partial)

    if matched_provider:
        extracted_hints.setdefault('vendor_name', matched_provider.vendor_name)
        extracted_hints.setdefault('category', matched_provider.category)
        logger.info(f"✅ Proveedor elegido (score {best_score}): {matched_provider.name}")
    else:
        logger.warning("⚠️ No se identificó un proveedor específico")
    
    logger.info(f"📊 Datos detectados por Regex: {json.dumps(extracted_hints, ensure_ascii=False)}")
    
    # Cargar instrucciones específicas del workflow
    workflow_instructions = load_agent_file("workflows/extraer-factura.md")
    
    prompt = f"""
    {CORE_RULES}
    
    {workflow_instructions}
    
    DATOS DETECTADOS POR REGEX (Priorízalos si existen):
    {json.dumps(extracted_hints, ensure_ascii=False, indent=2)}
    
    Extrae TODOS los siguientes campos en formato JSON:
    
    - invoice_number: {extracted_hints.get('invoice_number', 'Número de factura')}
    - date: {extracted_hints.get('date', 'Formato YYYY-MM-DD')}
    - vendor_name: {extracted_hints.get('vendor_name', 'Nombre de la empresa')}
    - total_amount: {extracted_hints.get('total_amount', 'Importe decimal')}
    - currency: EUR
    - type: "Purchase"
    - category: {extracted_hints.get('category', 'Telecom, Electricity, Gas, Water u Other')}
    - consumption: Número de consumo o null
    - consumption_unit: kWh, m3, GB o null
    - unit_price: Precio unitario o null
    - period: Periodo facturación
    - taxes: Impuestos totales
    - power: Potencia contratada o null
    - observations: Notas importantes o null
    
    Texto factura (primeros 2500 caracteres):
    {text[:2500]}
    
    Devuelve JSON válido.
    """
    
    final_data = {}
    try:
        # Usar la función unificada
        result_text = call_ai_service(prompt, json_format=True, db=db)
        
        # Limpieza básica por si el modelo devuelve markdown code blocks
        clean_text = result_text.replace("```json", "").replace("```", "").strip()
        final_data = json.loads(clean_text)
        
        # Post-procesamiento: forzar las ayudas detectadas por regex
        for key in ['invoice_number', 'date', 'category', 'vendor_name', 'total_amount']:
            if extracted_hints.get(key):
                final_data[key] = extracted_hints[key]

        # Guardar Log de Extracción en DB
        log = ExtractionLog(
            file_name=filename,
            raw_text=text[:5000],
            matching_scores=debug_scores,
            final_json=final_data
        )
        db.add(log)
        db.commit()
        
    except Exception as e:
        logger.error(f"❌ Error en Ollama o Guardado de Log: {e}")
        # Si falla la IA, devolvemos lo que tenemos de regex
        final_data = {
            "invoice_number": extracted_hints.get('invoice_number', "unknown"),
            "date": extracted_hints.get('date', None),
            "category": extracted_hints.get('category', "Other"),
            "vendor_name": extracted_hints.get('vendor_name', "Unknown"),
            "total_amount": extracted_hints.get('total_amount', 0.0),
            "currency": "EUR",
            "type": "Purchase",
            "notes": f"Extraído vía Regex (IA falló: {str(e)[:50]})"
        }

    return json.dumps(final_data, ensure_ascii=False)


def validate_invoice(invoice_data: dict, context: str = "", db: Session = None):
    """Workflow /validar_factura - Detectar errores de facturación"""
    # Cargar instrucciones workflow
    workflow_instructions = load_agent_file("workflows/validar-factura.md")

    prompt = f"""
    {CORE_RULES}
    
    {workflow_instructions}
    
    TAREA: Validar la siguiente factura y detectar errores típicos de facturación.
    
    Datos de la factura:
    {json.dumps(invoice_data, indent=2)}
    
    Contexto adicional (histórico):
    {context}
    
    FORMATO DE SALIDA (JSON):
    {{
        "status": "OK" | "REVISAR",
        "alerts": ["Lista de alertas"],
        "reasons": ["Motivos concretos"],
        "missing_fields": ["Campos faltantes"]
    }}
    """
    
    return call_ai_service(prompt, json_format=True, db=db)

def generate_kpis_direccion(invoices_data: list, db: Session = None):
    """Workflow /kpis_direccion - KPIs ejecutivos para dirección"""
    
    if not invoices_data:
        return json.dumps({
            "error": "No hay facturas para analizar",
            "gasto_total": 0,
            "numero_facturas": 0
        })
    
    # Cargar instrucciones workflow
    workflow_instructions = load_agent_file("workflows/kpis-direccion.md")

    prompt = f"""
    {CORE_RULES}
    
    {workflow_instructions}
    
    TAREA: Generar KPIs ejecutivos para presentación a dirección.
    
    Datos de facturas:
    {json.dumps(invoices_data, indent=2)}
    
    FORMATO DE SALIDA:
    ## KPIs PRINCIPALES
    [Lista de KPIs con valores]
    
    ## ANÁLISIS EJECUTIVO
    [2-3 bullets máximo con insights clave]
    
    ## ACCIONES RECOMENDADAS
    [Decisiones concretas para dirección]
    """
    
    return call_ai_service(prompt, db=db)

def generate_kpis_reclamacion(invoice_data: dict, contract_data: dict = None, historical_data: list = None, db: Session = None):
    """Workflow /kpis_reclamacion - Base técnica para reclamaciones"""
    # Cargar instrucciones workflow
    workflow_instructions = load_agent_file("workflows/kpis-reclamacion.md")

    prompt = f"""
    {CORE_RULES}
    
    {workflow_instructions}
    
    TAREA: Preparar base técnica para reclamar al proveedor.
    
    Factura a analizar:
    {json.dumps(invoice_data, indent=2)}
    
    Datos del contrato:
    {json.dumps(contract_data, indent=2) if contract_data else "No disponible"}
    
    Histórico:
    {json.dumps(historical_data, indent=2) if historical_data else "No disponible"}
    
    FORMATO DE SALIDA:
    ## PUNTOS RECLAMABLES
    [Lista numerada con evidencia]
    
    ## IMPACTO ECONÓMICO
    [Desglose por concepto]
    
    ## BASE ARGUMENTATIVA
    [Fundamentación técnica y normativa]
    """
    
    return call_ai_service(prompt, db=db)

def compare_supplier(current_invoice: dict, historical_invoices: list = None, alternative_supplier: dict = None, db: Session = None):
    """Workflow /comparar_proveedor - Benchmarking comparativo"""
    # Cargar instrucciones workflow
    workflow_instructions = load_agent_file("workflows/comparar-proveedor.md")

    prompt = f"""
    {CORE_RULES}
    
    {workflow_instructions}
    
    TAREA: Realizar benchmarking de proveedores.
    
    Factura actual:
    {json.dumps(current_invoice, indent=2)}
    
    Histórico del mismo proveedor:
    {json.dumps(historical_invoices, indent=2) if historical_invoices else "No disponible"}
    
    Proveedor alternativo:
    {json.dumps(alternative_supplier, indent=2) if alternative_supplier else "No disponible"}
    
    FORMATO DE SALIDA:
    ## COMPARATIVA DE PRECIOS
    [Tabla comparativa]
    
    ## AHORRO/SOBRECOSTO POTENCIAL
    [Cálculo con cifras]
    
    ## RECOMENDACIÓN
    [Mantener / Renegociar / Cambiar con justificación]
    """
    
    return call_ai_service(prompt, db=db)

def generate_meeting_summary(invoices_data: list, issues: list = None, db: Session = None):
    """Workflow /resumen_reunion - Mensaje ejecutivo para dirección"""
    # Cargar instrucciones workflow
    workflow_instructions = load_agent_file("workflows/resumen-reunion.md")

    prompt = f"""
    {CORE_RULES}
    
    {workflow_instructions}
    
    TAREA: Preparar mensaje ejecutivo para dirección.
    
    Datos de facturas del periodo:
    {json.dumps(invoices_data, indent=2)}
    
    Incidencias detectadas:
    {json.dumps(issues, indent=2) if issues else "Ninguna"}
    
    FORMATO DE SALIDA:
    ## RESUMEN EJECUTIVO
    • [Punto 1]
    • [Punto 2]
    • [Punto 3]
    • [Punto 4]
    • [Punto 5]
    
    ## DECISIÓN RECOMENDADA
    [Acción concreta]
    """
    
    return call_ai_service(prompt, db=db)

def check_alerts(invoice_data: dict, historical_avg: dict = None, thresholds: dict = None, db: Session = None):
    """Workflow /alertas - Detección de anomalías"""
    default_thresholds = {
        "consumption_increase_pct": 20,
        "price_deviation_pct": 15
    }
    thresholds = thresholds or default_thresholds
    
    # Cargar instrucciones workflow
    workflow_instructions = load_agent_file("workflows/alertas.md")
    
    prompt = f"""
    {CORE_RULES}
    
    {workflow_instructions}
    
    TAREA: Evaluar reglas de alerta y detectar anomalías.
    
    Factura actual:
    {json.dumps(invoice_data, indent=2)}
    
    Promedios históricos:
    {json.dumps(historical_avg, indent=2) if historical_avg else "No disponible"}
    
    Umbrales configurados:
    {json.dumps(thresholds, indent=2)}
    
    FORMATO DE SALIDA:
    ## ALERTAS DETECTADAS
    [Lista de alertas con severity: ALTA/MEDIA/BAJA]
    
    ## MAGNITUD DE DESVIACIÓN
    [Valores concretos]
    
    ## IMPACTO ECONÓMICO POTENCIAL
    [Estimación en €]
    
    ## ACCIÓN RECOMENDADA
    [Qué hacer con cada alerta]
    """
    
    return call_ai_service(prompt, db=db)

def chat_with_invoices(query: str, context: str, db: Session = None):
    """Chat mejorado con estructura profesional"""
    prompt = f"""
    {CORE_RULES}
    
    Datos disponibles:
    {context}
    
    Pregunta del usuario: {query}
    
    ESTRUCTURA DE RESPUESTA:
    1. KPIs relevantes (si aplica)
    2. Análisis de la situación
    3. Conclusiones o acciones recomendadas
    
    Si la información no está disponible, indícalo claramente y explica qué datos necesitarías.
    Mantén un tono profesional pero accesible.
    """
    
    return call_ai_service(prompt, db=db)


