# 🏭 Maintenance Wizard — Tata Steel AI Hackathon 2026

**Intelligent Agentic AI Maintenance Decision-Support System for Industrial Equipment**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini-1.5%20Flash-orange.svg)](https://aistudio.google.com)

---

## 🎯 Overview

Maintenance Wizard is an **agentic AI system** that acts as an intelligent maintenance decision-support platform for Tata Steel's industrial equipment. It goes beyond simple automation — it reasons, diagnoses, predicts, and recommends with explainability.

### Key Capabilities
- 🤖 **Multi-turn AI Chat** — Ask anything about equipment in natural language
- 🔍 **Anomaly Detection** — Isolation Forest ML model detects sensor anomalies in real-time
- 🔧 **Fault Diagnosis** — Rule-based knowledge base maps faults to root causes
- 🔮 **RUL Prediction** — RandomForest model predicts Remaining Useful Life
- ⚠️ **Risk Classification** — Multi-factor risk scoring (Low/Medium/High/Critical)
- 📄 **Report Generation** — Structured maintenance reports with Gemini AI narrative
- 📚 **RAG Knowledge Base** — Retrieval over equipment manuals, SOPs, historical logs

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│          Frontend Dashboard (HTML/CSS/JS)         │
│    Dashboard | Chat | Equipment | Alerts | Reports │
└─────────────────────┬───────────────────────────┘
                       │ REST API
┌─────────────────────▼───────────────────────────┐
│              FastAPI Backend (Python)             │
│                                                   │
│  ┌────────────────────────────────────────────┐  │
│  │        Orchestrator Agent                  │  │
│  │  Routes queries → coordinates sub-agents  │  │
│  └──┬─────────┬──────────┬──────────┬────────┘  │
│     │         │          │          │            │
│  ┌──▼──┐ ┌───▼──┐ ┌─────▼──┐ ┌────▼─────┐     │
│  │ RAG │ │Anomaly│ │Diagnos-│ │Prediction│     │
│  │Agent│ │Agent  │ │tic     │ │Agent(RUL)│     │
│  │     │ │(IF+   │ │Agent   │ │RandomFor-│     │
│  │Gem- │ │Rules) │ │(KB+    │ │est       │     │
│  │ini+ │ │       │ │Rules)  │ │          │     │
│  │Chro-│ └───────┘ └────────┘ └──────────┘     │
│  │maDB │                                         │
│  └─────┘ ┌──────────────────────────────┐       │
│           │     Report Agent (Gemini)    │       │
│           └──────────────────────────────┘       │
└─────────────────────────────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         │                            │
  ┌──────▼──────┐          ┌─────────▼──────┐
  │  ChromaDB   │          │  SQLite DB     │
  │ (Local RAG  │          │ (Feedback +    │
  │  vector DB) │          │  History)      │
  └─────────────┘          └────────────────┘
```

---

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| LLM | Google Gemini 1.5 Flash | Chat, RAG, Reports |
| Embeddings | sentence-transformers (local) | Document vectorization |
| Vector DB | ChromaDB (local) | Knowledge retrieval |
| Anomaly Detection | Isolation Forest (scikit-learn) | Sensor anomaly detection |
| RUL Prediction | Random Forest (scikit-learn) | Remaining Useful Life |
| Risk Classification | Rule-based engine | Risk scoring |
| Backend | FastAPI + Python | REST API server |
| Frontend | HTML + Vanilla CSS + JS | Dashboard UI |
| Charts | Chart.js | Data visualization |
| Storage | SQLite | Feedback & history |

**All components are free or open-source. Only one API key needed: Google Gemini (free tier).**

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- A free Gemini API key from [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

### Step 1: Get Your Free Gemini API Key
1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with Google (free)
3. Click "Create API Key"
4. Copy the key

### Step 2: Configure Environment
```bash
cd backend
copy .env.example .env
# Edit .env and set: GEMINI_API_KEY=your_key_here
```

### Step 3: Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 4: Run the Application
```bash
# Windows (double-click or run from terminal):
run.bat

# Or manually:
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 5: Open Dashboard
Open your browser and go to: **http://localhost:8000**

---

## 📁 Project Structure

```
agentic_ai_tatasteel/
├── backend/
│   ├── main.py                     # FastAPI application
│   ├── requirements.txt            # Python dependencies
│   ├── .env.example                # Environment config template
│   ├── agents/
│   │   ├── orchestrator.py         # Multi-agent coordinator
│   │   ├── rag_agent.py            # Gemini + ChromaDB RAG
│   │   ├── anomaly_agent.py        # Isolation Forest anomaly detection
│   │   ├── diagnostic_agent.py     # Fault diagnosis knowledge base
│   │   └── report_agent.py         # Report generation
│   ├── knowledge_base/
│   │   ├── vector_store.py         # ChromaDB wrapper
│   │   └── ingest.py               # Document ingestion pipeline
│   ├── models/
│   │   ├── rul_model.py            # RUL predictor (RandomForest)
│   │   └── risk_classifier.py      # Risk level classifier
│   ├── feedback/
│   │   └── feedback_store.py       # SQLite feedback storage
│   └── data/
│       ├── generate_data.py        # Synthetic data generator
│       ├── sample_sensor_data.csv  # 600 rows of sensor readings
│       ├── equipment_logs.csv      # 120 maintenance log entries
│       └── knowledge_docs/
│           ├── blast_furnace_manual.txt
│           ├── rolling_mill_sop.txt
│           ├── pump_compressor_guide.txt
│           └── conveyor_maintenance.txt
└── frontend/
    ├── index.html                  # Main dashboard
    ├── style.css                   # Dark industrial UI
    └── app.js                      # Dashboard JavaScript
```

---

## 🤖 Agent Pipeline

When you submit a query or sensor reading, the **Orchestrator** coordinates:

1. **RAG Agent** — Searches equipment manuals & SOPs with semantic similarity
2. **Anomaly Agent** — Runs Isolation Forest + threshold rules on sensor data
3. **Diagnostic Agent** — Maps fault codes to root causes using knowledge base
4. **Prediction Agent** — Estimates Remaining Useful Life with RandomForest
5. **Risk Classifier** — Scores risk (0-100) using multi-factor rules
6. **Report Agent** — Generates structured report with Gemini narrative

---

## 📊 Data Sources

### Synthetic Data (Auto-generated)
- **600 sensor readings** across 10 equipment units over 30 days
- **120 maintenance log entries** with realistic fault descriptions
- Equipment types: Blast Furnace, Rolling Mill, Pump, Compressor, Conveyor

### Knowledge Base Documents
- Blast Furnace maintenance manual
- Rolling Mill standard operating procedures
- Pump & Compressor maintenance guide
- Conveyor belt maintenance procedures

### Upload Your Own Documents
Use the **Knowledge Base** tab to upload PDF or TXT files. They will be automatically chunked, embedded, and indexed for retrieval.

---

## 💬 Sample Queries

Try these in the AI Chat:

- "What are the common causes of bearing failure in rolling mills?"
- "BF-01 is showing temperature 115°C — what should I do?"
- "Explain the emergency shutdown procedure for blast furnace"
- "What spare parts do I need for pump seal replacement?"
- "Analyze the vibration reading of 6.5 mm/s on COMP-01"
- "Create a maintenance schedule for the next week"

---

## 🔄 Feedback Loop

After each AI response, you can rate it 👍 or 👎. Feedback is stored in SQLite and used to:
- Track AI accuracy over time
- Identify knowledge gaps
- Improve future recommendations

---

## 📋 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard UI |
| GET | `/api/health` | System health |
| POST | `/api/chat` | Multi-turn AI chat |
| POST | `/api/analyze` | Full equipment analysis |
| GET | `/api/fleet/status` | All equipment status |
| GET | `/api/equipment/{id}/status` | Single equipment |
| POST | `/api/reports/generate` | Generate report |
| POST | `/api/feedback` | Submit feedback |
| POST | `/api/ingest` | Upload document |
| GET | `/api/kb/stats` | Knowledge base stats |

Full API docs at: **http://localhost:8000/docs**

---

## 🏆 Innovation Highlights

1. **Multi-Agent Architecture** — True orchestration of 5 specialist agents
2. **Hybrid Intelligence** — Rule-based + ML + LLM (not just LLM)
3. **Fully Local ML** — Anomaly detection and RUL run on-device
4. **Explainable AI** — Every recommendation cites source documents
5. **Feedback Loop** — Continuous improvement via engineer feedback
6. **Zero-cost ML** — No paid ML APIs — everything runs locally

---

*Tata Steel AI Hackathon 2026 — Team Submission*
