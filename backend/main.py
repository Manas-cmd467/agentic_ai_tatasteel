"""
Maintenance Wizard — FastAPI Backend
Main application entry point with all REST API endpoints.
"""
import os
import sys
import json
import sqlite3
from typing import Optional, List
from datetime import datetime, timedelta
import random

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

# ─── App initialization ───────────────────────────────────────────────────────

app = FastAPI(
    title="Maintenance Wizard API",
    description="Agentic AI Maintenance Decision-Support System for Tata Steel",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# ─── Global orchestrator (lazy initialized) ───────────────────────────────────

_orchestrator = None

def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from agents.orchestrator import MaintenanceOrchestrator
        _orchestrator = MaintenanceOrchestrator()
    return _orchestrator

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    equipment_context: Optional[dict] = None

class AnalyzeRequest(BaseModel):
    equipment_id: str
    equipment_type: Optional[str] = None
    vibration_mm_s: Optional[float] = None
    temperature_c: Optional[float] = None
    pressure_bar: Optional[float] = None
    current_amp: Optional[float] = None
    rpm: Optional[float] = None
    oil_level_pct: Optional[float] = None
    noise_db: Optional[float] = None
    fault_code: Optional[str] = None
    include_report: bool = False

class FeedbackRequest(BaseModel):
    session_id: str
    query: str
    ai_response: str
    rating: int  # 1-5
    comment: Optional[str] = None
    was_helpful: bool = True
    corrected_action: Optional[str] = None

class ReportRequest(BaseModel):
    equipment_id: str
    sensor_data: Optional[dict] = None

# ─── Startup / Shutdown ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize knowledge base and models on startup."""
    print("\n" + "="*60)
    print("🏭  MAINTENANCE WIZARD — TATA STEEL AI SYSTEM")
    print("="*60)

    # Run data generation if CSVs don't exist
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    sensor_csv = os.path.join(data_dir, "sample_sensor_data.csv")
    if not os.path.exists(sensor_csv):
        print("📊 Generating synthetic training data...")
        try:
            exec(open(os.path.join(data_dir, "generate_data.py")).read())
            print("  ✅ Synthetic data generated")
        except Exception as e:
            print(f"  ⚠️ Data generation skipped: {e}")

    # Initialize ChromaDB knowledge base
    try:
        from knowledge_base.ingest import run_ingestion_if_needed
        run_ingestion_if_needed()
    except Exception as e:
        print(f"  ⚠️ Knowledge base initialization: {e}")

    # Pre-warm orchestrator
    try:
        orch = get_orchestrator()
        print("✅ System ready!\n")
    except Exception as e:
        print(f"⚠️ Orchestrator init: {e}\n")


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main dashboard."""
    html_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Maintenance Wizard</h1><p>Frontend not found.</p>")


@app.get("/api/health")
async def health_check():
    """System health check."""
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    return {
        "status": "online",
        "system": "Maintenance Wizard",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "gemini_configured": bool(gemini_key and gemini_key != "your_gemini_api_key_here"),
        "components": {
            "rag_agent": "ready",
            "anomaly_agent": "ready",
            "diagnostic_agent": "ready",
            "report_agent": "ready",
        },
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Multi-turn conversational AI endpoint.
    Handles natural language queries with RAG + optional sensor context.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        orch = get_orchestrator()
        result = orch.chat(
            query=req.message,
            session_id=req.session_id,
            equipment_context=req.equipment_context,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze")
async def analyze_equipment(req: AnalyzeRequest):
    """
    Full agentic analysis pipeline for equipment sensor data.
    Runs: Anomaly → Diagnosis → RUL → Risk → Optional Report
    """
    sensor_data = req.dict()
    # Remove None values
    sensor_data = {k: v for k, v in sensor_data.items() if v is not None}
    
    if not sensor_data.get("equipment_id"):
        raise HTTPException(status_code=400, detail="equipment_id is required")
    
    try:
        orch = get_orchestrator()
        result = orch.analyze_equipment(
            sensor_data=sensor_data,
            include_report=req.include_report,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/equipment/{equipment_id}/status")
async def get_equipment_status(equipment_id: str):
    """
    Get live simulated equipment status with sensor readings.
    In production, this would connect to real SCADA/IoT systems.
    """
    # Generate realistic simulated data for the equipment
    eq_prefix = equipment_id.split("-")[0] if "-" in equipment_id else equipment_id
    
    # Base values per equipment type
    base_configs = {
        "BF": {"temp": 75, "vib": 1.8, "pres": 5.5, "curr": 140, "rpm": 0, "oil": 78},
        "RM": {"temp": 68, "vib": 2.1, "pres": 6.2, "curr": 165, "rpm": 1200, "oil": 72},
        "PUMP": {"temp": 58, "vib": 1.5, "pres": 5.0, "curr": 110, "rpm": 1450, "oil": 82},
        "CONV": {"temp": 52, "vib": 1.2, "pres": 0, "curr": 85, "rpm": 800, "oil": 75},
        "COMP": {"temp": 65, "vib": 1.9, "pres": 8.5, "curr": 130, "rpm": 2950, "oil": 70},
    }
    base = base_configs.get(eq_prefix, base_configs["PUMP"])
    
    # Add some randomness to simulate live data
    noise = lambda x, pct: x + random.uniform(-x * pct, x * pct)
    
    sensor_data = {
        "equipment_id": equipment_id,
        "equipment_type": eq_prefix,
        "timestamp": datetime.now().isoformat(),
        "vibration_mm_s": round(noise(base["vib"], 0.2), 2),
        "temperature_c": round(noise(base["temp"], 0.1), 1),
        "pressure_bar": round(noise(base["pres"], 0.15), 2) if base["pres"] else 0,
        "current_amp": round(noise(base["curr"], 0.15), 1),
        "rpm": round(noise(base["rpm"], 0.05), 0) if base["rpm"] else 0,
        "oil_level_pct": round(min(100, max(0, noise(base["oil"], 0.05))), 1),
        "noise_db": round(random.uniform(55, 70), 1),
        "fault_code": None,
    }
    
    # Occasionally inject anomaly (10% chance for demo)
    if random.random() < 0.10:
        fault = random.choice(["E001-BEARING_WEAR", "E002-OVERHEAT", "E006-VIBRATION_HIGH"])
        sensor_data["fault_code"] = fault
        sensor_data["vibration_mm_s"] = round(random.uniform(4.5, 7.5), 2)
        if fault == "E002-OVERHEAT":
            sensor_data["temperature_c"] = round(random.uniform(105, 135), 1)

    try:
        orch = get_orchestrator()
        analysis = orch.analyze_equipment(sensor_data)
        return {
            "equipment_id": equipment_id,
            "sensor_data": sensor_data,
            "analysis": analysis,
            "timestamp": sensor_data["timestamp"],
        }
    except Exception as e:
        return {
            "equipment_id": equipment_id,
            "sensor_data": sensor_data,
            "analysis": None,
            "error": str(e),
        }


@app.get("/api/fleet/status")
async def get_fleet_status():
    """Get status of all equipment in the fleet."""
    equipment_list = [
        "BF-01", "BF-02", "RM-01", "RM-02",
        "PUMP-01", "PUMP-02", "CONV-01", "CONV-02",
        "COMP-01", "COMP-02",
    ]
    
    statuses = []
    for eq_id in equipment_list:
        try:
            status = await get_equipment_status(eq_id)
            statuses.append({
                "equipment_id": eq_id,
                "equipment_type": eq_id.split("-")[0],
                "sensor_data": status["sensor_data"],
                "severity": status.get("analysis", {}).get("anomaly", {}).get("severity", "NORMAL"),
                "risk_level": status.get("analysis", {}).get("risk", {}).get("risk_level", "LOW"),
                "rul_hours": status.get("analysis", {}).get("rul", {}).get("rul_hours", 500),
                "alerts": status.get("analysis", {}).get("anomaly", {}).get("alerts", []),
            })
        except Exception:
            statuses.append({
                "equipment_id": eq_id,
                "severity": "NORMAL",
                "risk_level": "LOW",
                "error": "Status unavailable",
            })
    
    # Aggregate summary
    critical = sum(1 for s in statuses if s.get("severity") == "CRITICAL")
    high = sum(1 for s in statuses if s.get("severity") == "HIGH")
    medium = sum(1 for s in statuses if s.get("severity") == "MEDIUM")
    normal = sum(1 for s in statuses if s.get("severity") == "NORMAL")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_equipment": len(equipment_list),
        "summary": {
            "critical": critical,
            "high": high,
            "medium": medium,
            "normal": normal,
            "overall_health_pct": round(100 * normal / max(len(equipment_list), 1), 1),
        },
        "equipment": statuses,
    }


@app.post("/api/reports/generate")
async def generate_report(req: ReportRequest):
    """Generate a structured maintenance report for equipment."""
    try:
        orch = get_orchestrator()
        report = orch.generate_report(
            equipment_id=req.equipment_id,
            sensor_data=req.sensor_data,
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/list")
async def list_reports():
    """List saved maintenance reports."""
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    reports = []
    if os.path.exists(reports_dir):
        for fname in sorted(os.listdir(reports_dir), reverse=True)[:20]:
            if fname.endswith(".json"):
                fpath = os.path.join(reports_dir, fname)
                try:
                    with open(fpath) as f:
                        data = json.load(f)
                    reports.append({
                        "report_id": data.get("report_id", fname),
                        "equipment_id": data.get("equipment_id"),
                        "timestamp": data.get("timestamp"),
                        "summary": data.get("summary"),
                        "filename": fname,
                    })
                except Exception:
                    pass
    
    return {"reports": reports, "total": len(reports)}


@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Submit engineer feedback to improve AI recommendations."""
    try:
        from feedback.feedback_store import FeedbackStore
        store = FeedbackStore()
        feedback_id = store.save_feedback(
            session_id=req.session_id,
            query=req.query,
            response=req.ai_response,
            rating=req.rating,
            comment=req.comment or "",
            was_helpful=req.was_helpful,
        )
        
        stats = store.get_feedback_stats()
        return {
            "status": "saved",
            "feedback_id": feedback_id,
            "message": "Thank you for your feedback! It helps improve the Maintenance Wizard.",
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feedback/stats")
async def get_feedback_stats():
    """Get feedback statistics."""
    try:
        from feedback.feedback_store import FeedbackStore
        store = FeedbackStore()
        return store.get_feedback_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest")
async def ingest_document(file: UploadFile = File(...)):
    """Upload and index a new knowledge document."""
    import tempfile
    
    if not file.filename.endswith((".txt", ".pdf", ".md")):
        raise HTTPException(
            status_code=400,
            detail="Only .txt, .pdf, and .md files are supported"
        )
    
    # Save to knowledge docs dir
    docs_dir = os.path.join(
        os.path.dirname(__file__), "data", "knowledge_docs"
    )
    os.makedirs(docs_dir, exist_ok=True)
    save_path = os.path.join(docs_dir, file.filename)
    
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    
    # Re-ingest
    try:
        from knowledge_base.ingest import ingest_all_documents
        from knowledge_base.vector_store import VectorStore
        vs = VectorStore()
        count = ingest_all_documents(docs_dir, vs)
        return {
            "status": "indexed",
            "filename": file.filename,
            "chunks_added": count,
            "message": f"Document '{file.filename}' indexed with {count} chunks",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kb/stats")
async def knowledge_base_stats():
    """Get knowledge base statistics."""
    try:
        from knowledge_base.vector_store import VectorStore
        vs = VectorStore()
        stats = vs.get_collection_stats()
        return stats
    except Exception as e:
        return {"error": str(e), "total_documents": 0}


@app.get("/api/sensor/history/{equipment_id}")
async def get_sensor_history(equipment_id: str, hours: int = 24):
    """Get simulated sensor history for charts."""
    # Simulate historical data
    data_points = []
    now = datetime.now()
    eq_prefix = equipment_id.split("-")[0]
    
    base_configs = {
        "BF": {"temp": 75, "vib": 1.8},
        "RM": {"temp": 68, "vib": 2.1},
        "PUMP": {"temp": 58, "vib": 1.5},
        "CONV": {"temp": 52, "vib": 1.2},
        "COMP": {"temp": 65, "vib": 1.9},
    }
    base = base_configs.get(eq_prefix, base_configs["PUMP"])
    
    for i in range(hours * 4):  # every 15 min
        ts = now - timedelta(minutes=15 * (hours * 4 - i))
        noise = lambda x, pct: x + random.uniform(-x * pct, x * pct)
        data_points.append({
            "timestamp": ts.isoformat(),
            "vibration_mm_s": round(noise(base["vib"], 0.25), 2),
            "temperature_c": round(noise(base["temp"], 0.1), 1),
        })
    
    return {
        "equipment_id": equipment_id,
        "hours": hours,
        "data": data_points,
    }


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation session."""
    try:
        orch = get_orchestrator()
        orch.reset_session(session_id)
        return {"status": "cleared", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
