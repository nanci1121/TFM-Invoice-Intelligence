from fastapi import FastAPI, UploadFile, File, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import os
from .ai_service import (
    extract_invoice_data, chat_with_invoices, get_text_from_image, get_text_from_pdf,
    validate_invoice, generate_kpis_direccion, generate_kpis_reclamacion,
    compare_supplier, generate_meeting_summary, check_alerts
)
import os
from pydantic import BaseModel
from .database import SessionLocal, init_db, Invoice, get_db, Provider, ExtractionLog, SystemSetting
from sqlalchemy.orm import Session
from fastapi import Depends
from datetime import datetime
import json
import re
from typing import Optional, List
from pathlib import Path

# Ensure DB is initialized (only in non-testing mode)
if not os.getenv("TESTING", "false").lower() == "true":
    init_db()

# Sync initial providers if table is empty
def sync_providers_from_json():
    db = SessionLocal()
    try:
        count = db.query(Provider).count()
        if count == 0:
            json_path = Path(__file__).parent / "invoice_patterns.json"
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for p_data in data.get('providers', []):
                        provider = Provider(
                            name=p_data['name'],
                            vendor_name=p_data['vendor_name'],
                            category=p_data['category'],
                            patterns=p_data['patterns']
                        )
                        db.add(provider)
                    db.commit()
    except Exception as e:
        print(f"Error syncing providers: {e}")
    finally:
        db.close()

# Only sync providers in non-testing mode
if not os.getenv("TESTING", "false").lower() == "true":
    sync_providers_from_json()

class ChatRequest(BaseModel):
    query: str

class WorkflowRequest(BaseModel):
    model_config = {"extra": "allow"}  # Allow extra fields for flexibility
    invoice_id: Optional[int] = None
    data: Optional[dict] = None
    invoice_data: Optional[dict] = None
    invoices: Optional[List[dict]] = None
    historical_data: Optional[List[dict]] = None
    current_invoice: Optional[dict] = None
    market_data: Optional[dict] = None
    period: Optional[str] = None
    thresholds: Optional[dict] = None

app = FastAPI(title="Invoice Reader API")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/invoices")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434/api/generate")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from frontend directory (only if it exists)
frontend_path = os.path.join(os.getcwd(), "frontend")
if not os.path.exists(frontend_path):
    # Fallback for Docker environment
    frontend_path = "/app/frontend"

# Only mount frontend if directory exists (to allow tests to run)
if os.path.exists(frontend_path):
    app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")

@app.get("/")
async def health_check():
    """Health check endpoint for monitoring and tests"""
    return {"status": "healthy", "service": "Invoice Reader API"}

@app.get("/app")
async def read_root():
    """Redirect to frontend application"""
    return RedirectResponse(url="/frontend/index.html")

UPLOAD_DIR = "backend/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =============================================================================
# RESCATE POR REGEX: Busca datos faltantes directamente en el texto del PDF
# Primero usa los patrones del proveedor (configurables desde admin.html),
# luego usa patrones genéricos como fallback.
# =============================================================================
def rescue_with_regex(data: dict, raw_text: str, db: Session = None) -> dict:
    """
    Si la IA dejó campos como 'unknown' o vacíos, 
    busca directamente en el raw_text con regex.
    
    1º Intenta con patrones específicos del proveedor (de la tabla Provider en DB).
    2º Si no encuentra, usa patrones genéricos hardcoded como fallback.
    """
    if not raw_text:
        return data
    
    # --- Cargar patrones específicos del proveedor desde la DB ---
    provider_patterns = {}
    if db:
        providers = db.query(Provider).all()
        for prov in providers:
            # Buscar si algún patrón de "vendor" coincide con el texto
            if prov.patterns and prov.patterns.get("vendor"):
                for vendor_pattern in prov.patterns["vendor"]:
                    try:
                        if re.search(vendor_pattern, raw_text, re.IGNORECASE):
                            provider_patterns = prov.patterns
                            print(f"🔧 REGEX RESCUE: Proveedor detectado: {prov.name}")
                            break
                    except re.error:
                        pass
                if provider_patterns:
                    break
    
    # --- NÚMERO DE FACTURA ---
    if not data.get("invoice_number") or data.get("invoice_number") == "unknown":
        # 1º: Patrones del proveedor (de la DB, configurables desde admin.html)
        db_invoice_patterns = provider_patterns.get("invoice_number", [])
        # 2º: Patrones genéricos (fallback)
        generic_invoice_patterns = [
            r'N\.?\s*º?\s*(?:de\s+)?(?:factura|fact\.?)\s*[:.]?\s*([A-Z0-9][\w\-/]{3,20})',
            r'(?:Factura|Invoice)\s*(?:N[ºo°]?|#|número)?\s*[:.]?\s*([A-Z0-9][\w\-/]{3,20})',
            r'(FE\d{8,12})',
            r'(FA\d{4,}[\-/]?\d*)',
            r'Nº\s*Factura\s*[:.]?\s*([A-Z0-9][\w\-/]{3,20})',
        ]
        
        all_patterns = db_invoice_patterns + generic_invoice_patterns
        for pattern in all_patterns:
            try:
                match = re.search(pattern, raw_text, re.IGNORECASE)
                if match:
                    invoice_num = match.group(1).strip()
                    if len(invoice_num) >= 4:
                        source = "DB" if pattern in db_invoice_patterns else "genérico"
                        data["invoice_number"] = invoice_num
                        print(f"🔧 REGEX RESCUE ({source}): Nº factura = {invoice_num}")
                        break
            except re.error as e:
                print(f"⚠️ Regex inválido (invoice_number): {pattern} → {e}")
    
    # --- FECHA DE FACTURA ---
    if not data.get("date") or data.get("date") == "unknown":
        db_date_patterns = provider_patterns.get("date", [])
        generic_date_patterns = [
            r'[Ff]echa\s+(?:de\s+la\s+)?factura\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'[Ff]echa\s+(?:de\s+)?emisi[oó]n\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'[Ff]echa\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        ]
        
        all_patterns = db_date_patterns + generic_date_patterns
        for pattern in all_patterns:
            try:
                match = re.search(pattern, raw_text)
                if match:
                    # Handle multi-group patterns (DD)(MM)(YYYY) or single-group DD/MM/YYYY
                    groups = [g for g in match.groups() if g]
                    if len(groups) == 3:
                        # Pattern captured (DD)(MM)(YYYY) separately
                        day, month, year = groups
                    elif len(groups) == 1:
                        # Pattern captured DD/MM/YYYY as single group
                        date_raw = groups[0].strip()
                        parts = re.split(r'[/-]', date_raw)
                        if len(parts) == 3:
                            day, month, year = parts
                        else:
                            continue
                    else:
                        continue
                    
                    if len(year) == 2:
                        year = "20" + year
                    try:
                        source = "DB" if pattern in db_date_patterns else "genérico"
                        data["date"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        print(f"🔧 REGEX RESCUE ({source}): Fecha = {data['date']}")
                        break
                    except:
                        pass
            except re.error as e:
                print(f"⚠️ Regex inválido (date): {pattern} → {e}")
    
    # --- CONSUMO (kWh, m³) ---
    if not data.get("consumption") or float(data.get("consumption", 0)) == 0:
        db_consumption_patterns = provider_patterns.get("consumption", [])
        generic_consumption_patterns = [
            r'Total\s+periodo\s*\(?\d?\)?\s*(\d+[\.,]?\d*)\s+(\d+[\.,]?\d*)\s+(\d+[\.,]?\d*)',
            r'[Cc]onsumo\s+(?:total|periodo)\s*[:.]?\s*(\d+[\.,]?\d*)\s*(kWh|m[³3]|litros?)',
            r'(\d+[\.,]?\d*)\s*kWh\s*(?:total|consumidos?)',
        ]
        
        all_patterns = db_consumption_patterns + generic_consumption_patterns
        for pattern in all_patterns:
            try:
                match = re.search(pattern, raw_text)
                if match:
                    groups = [g for g in match.groups() if g]
                    # Sum Punta+Llano+Valle if 3 numeric groups
                    numeric_groups = [g for g in groups if g.replace(',', '.').replace('.', '', 1).isdigit()]
                    if len(numeric_groups) == 3:
                        total = sum(float(g.replace(',', '.')) for g in numeric_groups)
                        data["consumption"] = total
                        data["consumption_unit"] = "kWh"
                        source = "DB" if pattern in db_consumption_patterns else "genérico"
                        print(f"🔧 REGEX RESCUE ({source}): Consumo (P+L+V) = {total} kWh")
                        break
                    elif len(numeric_groups) >= 1:
                        val = float(numeric_groups[0].replace(',', '.'))
                        if val > 0:
                            data["consumption"] = val
                            data["consumption_unit"] = "kWh"
                            source = "DB" if pattern in db_consumption_patterns else "genérico"
                            print(f"🔧 REGEX RESCUE ({source}): Consumo = {val} kWh")
                            break
            except re.error as e:
                print(f"⚠️ Regex inválido (consumption): {pattern} → {e}")

    return data

@app.post("/upload")
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    # Check if file already exists
    existing = db.query(Invoice).filter(Invoice.file_path.contains(file.filename)).first()
    if existing:
        return {
            "status": "error", 
            "message": f"Esta factura ya existe (Nº {existing.invoice_number}). No se permiten duplicados."
        }
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Real Extraction (PDF or Image)
    if file.filename.lower().endswith(".pdf"):
        raw_text = get_text_from_pdf(file_path)
    else:
        raw_text = get_text_from_image(file_path)
    
    if not raw_text or "Error" in raw_text:
        # If text extraction failed, it might be a scanned PDF image-only
        # For simplicity in this TFM, we focus on searchable PDFs or images
        pass

    extracted_json = extract_invoice_data(raw_text, db, file.filename)
    
    try:
        data = json.loads(extracted_json)
        
        # === RESCATE POR REGEX: Si la IA dejó campos vacíos, los buscamos en el texto ===
        data = rescue_with_regex(data, raw_text, db=db)
        
        # Parse date from extracted data
        invoice_date = datetime.now()  # Default fallback
        if data.get("date"):
            try:
                # Try multiple date formats
                date_str = data.get("date")
                print(f"🔍 Intentando parsear fecha: {date_str}")
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
                    try:
                        invoice_date = datetime.strptime(date_str, fmt)
                        print(f"✅ Fecha parseada correctamente: {invoice_date} usando formato {fmt}")
                        break
                    except ValueError:
                        continue
                else:
                    print(f"⚠️ No se pudo parsear la fecha '{date_str}', usando fecha actual")
            except Exception as e:
                print(f"❌ Error al parsear fecha: {e}")
        else:
            print(f"⚠️ No se extrajo fecha de la factura, usando fecha actual")
        
        # Check for duplicate invoice number
        if data.get("invoice_number") and data.get("invoice_number") != "unknown":
            existing_invoice = db.query(Invoice).filter(
                Invoice.invoice_number == data.get("invoice_number")
            ).first()
            if existing_invoice:
                os.remove(file_path)  # Delete uploaded file
                return {
                    "status": "error",
                    "message": f"Factura duplicada: Ya existe la factura Nº {data.get('invoice_number')}"
                }
        
        # Save to DB
        new_invoice = Invoice(
            invoice_number=data.get("invoice_number", "unknown"),
            date=invoice_date,
            vendor_name=data.get("vendor_name", "unknown"),
            total_amount=float(data.get("total_amount") or 0),
            currency=data.get("currency", "EUR"),
            type=data.get("type", "Purchase"),
            file_path=file_path,
            category=data.get("category", "Other"),
            consumption=float(data.get("consumption") or 0),
            consumption_unit=data.get("consumption_unit", ""),
            raw_text=raw_text
        )
        db.add(new_invoice)
        db.commit()
        db.refresh(new_invoice)
        
        return {
            "status": "success",
            "message": f"Factura procesada: {new_invoice.invoice_number}",
            "raw_text": raw_text,
            "invoice": {
                "id": new_invoice.id,
                "invoice_number": new_invoice.invoice_number,
                "vendor": new_invoice.vendor_name,
                "total": new_invoice.total_amount
            }
        }
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return {"status": "error", "message": str(e)}

@app.get("/reports")
def get_reports(db: Session = Depends(get_db)):
    invoices = db.query(Invoice).all()
    return invoices

@app.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Improved Context Selection based on Query
    query_lower = request.query.lower()
    
    # 1. Filter invoices based on keywords in query (e.g. "Som Energia", "diciembre")
    all_invoices = db.query(Invoice).all()
    relevant_invoices = []
    
    for inv in all_invoices:
        # Check for vendor match (check if ANY word from vendor appears in query)
        if inv.vendor_name:
            vendor_words = inv.vendor_name.lower().replace(",", "").split()
            # Match if at least 2 words match, or 1 word if vendor has only 1 word
            matches = sum(1 for w in vendor_words if len(w) > 2 and w in query_lower)
            if matches >= 1:
                relevant_invoices.append(inv)
                continue
            
        # Check for category match (e.g. "luz", "electricidad")
        if inv.category and inv.category.lower() in query_lower:
            relevant_invoices.append(inv)
            continue
            
        # Check for month/year match in date
        if inv.date:
            date_str = str(inv.date)
            # Simple check if YYYY-MM is in query
            if date_str[:7] in request.query: 
                relevant_invoices.append(inv)
                continue
    
    # Fallback: if no specific filtering, use all invoices (but limit text size)
    if not relevant_invoices:
        relevant_invoices = all_invoices

    context = ""
    # ESTRATEGIA: Solo incluir RAW TEXT si el usuario pregunta por un proveedor específico
    # para no agotar la cuota de tokens con preguntas generales.
    include_raw_text = False
    if relevant_invoices and len(relevant_invoices) < len(all_invoices):
        # Si hemos filtrado (ej: "de Som Energia"), entonces sí queremos el detalle
        include_raw_text = True
    
    # DEBUG LOG
    print(f"🔍 CHAT DEBUG: Query='{request.query}', Relevant={len(relevant_invoices)}/{len(all_invoices)}, IncludeRawText={include_raw_text}")
    
    for inv in relevant_invoices:
        context += f"=== FACTURA ID {inv.id} ===\n"
        
        # RAW TEXT FIRST (most important for the AI to read)
        if include_raw_text and inv.raw_text:
            context += f"TEXTO COMPLETO DEL PDF (FUENTE PRINCIPAL - LEE ESTO PRIMERO):\n"
            context += f"{inv.raw_text[:2000]}\n"
            context += f"--- FIN TEXTO PDF ---\n"
        
        # Structured data SECOND (only show non-unknown fields)
        context += f"DATOS EXTRAÍDOS AUTOMÁTICAMENTE:\n"
        context += f"  Proveedor: {inv.vendor_name}\n"
        context += f"  Total: {inv.total_amount} {inv.currency}\n"
        context += f"  Categoría: {inv.category}\n"
        
        if inv.invoice_number and inv.invoice_number != "unknown":
            context += f"  Nº Factura: {inv.invoice_number}\n"
        else:
            context += f"  Nº Factura: (NO EXTRAÍDO - BUSCAR EN TEXTO DEL PDF ARRIBA)\n"
            
        if inv.consumption and inv.consumption > 0:
            context += f"  Consumo: {inv.consumption} {inv.consumption_unit}\n"
        
        context += "\n"
    
    # DEBUG LOG
    print(f"📝 CHAT DEBUG: Contexto total = {len(context)} caracteres")
    print(f"📝 CHAT DEBUG: Contiene 'N.º de factura'? {'Sí' if 'N.º de factura' in context else 'No'}")
    
    if not context:
        context = "No hay facturas procesadas todavía."
        
    response = chat_with_invoices(request.query, context, db=db)
    return {"response": response}

@app.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return {"status": "error", "message": "Invoice not found"}
    
    # Store info for response
    invoice_number = invoice.invoice_number
    file_path = invoice.file_path
    
    # Delete from database first
    db.delete(invoice)
    db.commit()
    
    # Then delete physical file if it exists
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"✅ Archivo eliminado: {file_path}")
        except Exception as e:
            print(f"⚠️ Error al eliminar archivo: {str(e)}")
            # Don't fail if file deletion fails, as DB record is already deleted

    return {
        "status": "success", 
        "message": f"Factura {invoice_number} eliminada correctamente (ID: {invoice_id})"
    }

@app.get("/advanced-stats")
def get_advanced_stats(db: Session = Depends(get_db)):
    invoices = db.query(Invoice).all()
    
    # Category distribution
    categories = {}
    total_cost = 0
    
    for inv in invoices:
        cat = inv.category or "Other"
        categories[cat] = categories.get(cat, 0) + inv.total_amount
        total_cost += inv.total_amount
    
    distribution = [
        {"name": cat, "value": amt, "percent": (amt/total_cost*100) if total_cost > 0 else 0}
        for cat, amt in categories.items()
    ]
    
    # Efficiency KPIs (simplified: average cost per unit by category)
    efficiency = []
    cat_consumption = {}
    for inv in invoices:
        if inv.consumption and inv.consumption > 0:
            cat = inv.category or "Other"
            if cat not in cat_consumption:
                cat_consumption[cat] = {"cost": 0, "units": 0, "unit": inv.consumption_unit}
            cat_consumption[cat]["cost"] += inv.total_amount
            cat_consumption[cat]["units"] += inv.consumption
            
    for cat, data in cat_consumption.items():
        efficiency.append({
            "category": cat,
            "cost_per_unit": data["cost"] / data["units"],
            "unit": data["unit"]
        })
        
    return {
        "distribution": distribution,
        "efficiency": efficiency,
        "total_cost": total_cost,
        "invoice_count": len(invoices)
    }

# ============== WORKFLOW ENDPOINTS ==============

@app.post("/workflow/validar-factura")
async def workflow_validate_invoice(request: WorkflowRequest, db: Session = Depends(get_db)):
    """Workflow: Validar factura y detectar errores"""
    # Handle different input formats from tests
    if request.invoice_id:
        invoice = db.query(Invoice).filter(Invoice.id == request.invoice_id).first()
        if not invoice:
            return {"status": "error", "message": "Factura no encontrada"}
        
        invoice_data = {
            "invoice_number": invoice.invoice_number,
            "vendor": invoice.vendor_name,
            "total": invoice.total_amount,
            "consumption": invoice.consumption,
            "unit": invoice.consumption_unit,
            "category": invoice.category
        }
    elif request.invoice_data:
        invoice_data = request.invoice_data
    else:
        invoice_data = request.data
    
    # Get context from other invoices
    invoices = db.query(Invoice).all()
    context = f"Histórico de {len(invoices)} facturas procesadas"
    
    result = validate_invoice(invoice_data, context, db=db)
    # Parse JSON result if it's a string
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            pass
    return result if isinstance(result, dict) else {"status": "success", "result": result}

@app.post("/workflow/kpis-direccion")
async def workflow_kpis_direccion(request: WorkflowRequest = None, db: Session = Depends(get_db)):
    """Workflow: Generar KPIs para dirección"""
    # Use invoices from request if provided, otherwise from DB
    if request and request.invoices:
        invoices_data = request.invoices
    else:
        invoices = db.query(Invoice).all()
        invoices_data = [
            {
                "id": inv.id,
                "vendor": inv.vendor_name,
                "category": inv.category,
                "total": inv.total_amount,
                "consumption": inv.consumption,
                "unit": inv.consumption_unit,
                "date": str(inv.date)
            }
            for inv in invoices
        ]
    
    result = generate_kpis_direccion(invoices_data, db=db)
    # Parse JSON result if it's a string
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            pass
    return result if isinstance(result, dict) else {"status": "success", "result": result}

@app.post("/workflow/kpis-reclamacion")
async def workflow_kpis_reclamacion(request: WorkflowRequest, db: Session = Depends(get_db)):
    """Workflow: Preparar base técnica para reclamación"""
    # Handle different input formats
    if request.invoice_data:
        invoice_data = request.invoice_data
        historical_data = request.historical_data or []
    elif request.invoice_id:
        invoice = db.query(Invoice).filter(Invoice.id == request.invoice_id).first()
        if not invoice:
            return {"status": "error", "message": "Factura no encontrada"}
        
        invoice_data = {
            "invoice_number": invoice.invoice_number,
            "vendor": invoice.vendor_name,
            "total": invoice.total_amount,
            "consumption": invoice.consumption,
            "unit": invoice.consumption_unit,
            "category": invoice.category
        }
        
        # Get historical data for same category
        historical = db.query(Invoice).filter(
            Invoice.category == invoice.category,
            Invoice.id != invoice.id
        ).all()
        
        historical_data = [
            {
                "vendor": h.vendor_name,
                "total": h.total_amount,
                "consumption": h.consumption,
                "date": str(h.date)
            }
            for h in historical
        ]
    else:
        return {"status": "error", "message": "invoice_id o invoice_data requerido"}
    
    result = generate_kpis_reclamacion(invoice_data, historical_data=historical_data, db=db)
    # Parse JSON result if it's a string
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            pass
    return result if isinstance(result, dict) else {"status": "success", "result": result}

@app.post("/workflow/comparar-proveedor")
async def workflow_compare_supplier(request: WorkflowRequest, db: Session = Depends(get_db)):
    """Workflow: Comparar proveedores"""
    # Handle different input formats
    if request.current_invoice:
        current_invoice = request.current_invoice
        historical_invoices = []
    elif request.invoice_id:
        invoice = db.query(Invoice).filter(Invoice.id == request.invoice_id).first()
        if not invoice:
            return {"status": "error", "message": "Factura no encontrada"}
        
        current_invoice = {
            "vendor": invoice.vendor_name,
            "total": invoice.total_amount,
            "consumption": invoice.consumption,
            "unit": invoice.consumption_unit,
            "category": invoice.category
        }
        
        # Get historical invoices from same vendor
        historical = db.query(Invoice).filter(
            Invoice.vendor_name == invoice.vendor_name,
            Invoice.id != invoice.id
        ).all()
        
        historical_invoices = [
            {
                "total": h.total_amount,
                "consumption": h.consumption,
                "date": str(h.date)
            }
            for h in historical
        ]
    else:
        return {"status": "error", "message": "invoice_id o current_invoice requerido"}
    
    result = compare_supplier(current_invoice, historical_invoices, db=db)
    # Parse JSON result if it's a string
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            pass
    return result if isinstance(result, dict) else {"status": "success", "result": result}

@app.post("/workflow/resumen-reunion")
async def workflow_meeting_summary(request: WorkflowRequest = None, db: Session = Depends(get_db)):
    """Workflow: Generar resumen para reunión ejecutiva"""
    # Use invoices from request if provided, otherwise from DB
    if request and request.invoices is not None:
        invoices_data = request.invoices
    else:
        invoices = db.query(Invoice).all()
        invoices_data = [
            {
                "vendor": inv.vendor_name,
                "category": inv.category,
                "total": inv.total_amount,
                "date": str(inv.date)
            }
            for inv in invoices
        ]
    
    result = generate_meeting_summary(invoices_data, db=db)
    # Parse JSON result if it's a string
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            pass
    return result if isinstance(result, dict) else {"status": "success", "result": result}

@app.post("/workflow/alertas")
async def workflow_check_alerts(request: WorkflowRequest, db: Session = Depends(get_db)):
    """Workflow: Detectar alertas y anomalías"""
    # Handle different input formats
    if request.invoices:
        # Test format with invoices list
        invoice_data = request.invoices[0] if request.invoices else {}
        historical_avg = None
    elif request.invoice_id:
        invoice = db.query(Invoice).filter(Invoice.id == request.invoice_id).first()
        if not invoice:
            return {"status": "error", "message": "Factura no encontrada"}
        
        invoice_data = {
            "vendor": invoice.vendor_name,
            "total": invoice.total_amount,
            "consumption": invoice.consumption,
            "category": invoice.category
        }
        
        # Calculate historical average
        historical = db.query(Invoice).filter(
            Invoice.category == invoice.category,
            Invoice.id != invoice.id
        ).all()
        
        if historical:
            avg_consumption = sum(h.consumption or 0 for h in historical) / len(historical)
            avg_total = sum(h.total_amount for h in historical) / len(historical)
            historical_avg = {
                "avg_consumption": avg_consumption,
                "avg_total": avg_total
            }
        else:
            historical_avg = None
    else:
        return {"status": "error", "message": "invoice_id o invoices requerido"}
    
    result = check_alerts(invoice_data, historical_avg, db=db)
    # Parse JSON result if it's a string
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            pass
    return result if isinstance(result, dict) else {"status": "success", "result": result}

# Endpoints para gestionar patrones de proveedores (ahora en DB)
@app.get("/admin/patterns")
async def get_patterns(db: Session = Depends(get_db)):
    """Obtiene la configuración actual de los proveedores desde la DB"""
    try:
        providers = db.query(Provider).all()
        result = []
        for p in providers:
            result.append({
                "name": p.name,
                "vendor_name": p.vendor_name,
                "category": p.category,
                "patterns": p.patterns
            })
        return {"status": "success", "patterns": {"providers": result}}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/admin/patterns")
async def save_patterns(payload: dict, db: Session = Depends(get_db)):
    """Guarda la configuración de proveedores en la DB"""
    try:
        # Por simplicidad, truncamos y recreamos (o actualizamos si prefieres)
        # En una app real haríamos un upsert más fino
        db.query(Provider).delete()
        for p_data in payload.get('providers', []):
            new_p = Provider(
                name=p_data['name'],
                vendor_name=p_data['vendor_name'],
                category=p_data['category'],
                patterns=p_data['patterns']
            )
            db.add(new_p)
        db.commit()
        return {"status": "success", "message": "Proveedores actualizados en DB correctamente"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

@app.get("/admin/logs")
async def get_extraction_logs(db: Session = Depends(get_db)):
    """Obtiene los últimos registros de extracción para depuración"""
    logs = db.query(ExtractionLog).order_by(ExtractionLog.timestamp.desc()).limit(10).all()
    return {"status": "success", "logs": logs}

# ============== SETTINGS ENDPOINTS ==============

@app.get("/api/settings")
async def get_settings(db: Session = Depends(get_db)):
    """Obtiene la configuración de IA de la base de datos"""
    settings = db.query(SystemSetting).all()
    result = {s.key: s.value for s in settings}
    
    # Valores por defecto si no existen en DB
    if "AI_PROVIDER" not in result:
        result["AI_PROVIDER"] = os.getenv("AI_PROVIDER", "ollama")
    if "GEMINI_API_KEY" not in result:
        result["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
    if "OPENAI_API_KEY" not in result:
        result["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")
        
    return {"status": "success", "settings": result}

@app.post("/api/settings")
async def save_settings(payload: dict, db: Session = Depends(get_db)):
    """Guarda la configuración de IA en la base de datos"""
    try:
        for key, value in payload.items():
            setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if setting:
                setting.value = value
            else:
                new_setting = SystemSetting(key=key, value=value)
                db.add(new_setting)
        db.commit()
        return {"status": "success", "message": "Configuración guardada correctamente"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

