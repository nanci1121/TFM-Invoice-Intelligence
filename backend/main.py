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
            consumption_unit=data.get("consumption_unit", "")
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
    # Fetch all data as context
    invoices = db.query(Invoice).all()
    context = ""
    for inv in invoices:
        context += f"Factura {inv.invoice_number}: PROVEEDOR {inv.vendor_name}, TOTAL {inv.total_amount} {inv.currency}, TIPO {inv.type}, FECHA {inv.date}.\n"
    
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

