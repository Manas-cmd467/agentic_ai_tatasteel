"""
Maintenance Wizard — Multi-Agent Orchestrator
The brain that coordinates all specialist agents.
Routes queries, aggregates results, and manages conversation state.
"""
import os
import sys
import json
from typing import Optional
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.rag_agent import RAGAgent
from agents.anomaly_agent import AnomalyDetectionAgent
from agents.diagnostic_agent import diagnose_fault
from agents.report_agent import ReportAgent


class MaintenanceOrchestrator:
    """
    Central orchestrator that coordinates all maintenance AI agents.
    
    Agent Pipeline:
    User Input → [Route Intent] → [RAG Agent] → [Anomaly Agent] 
                                → [Diagnostic Agent] → [RUL Predictor]
                                → [Risk Classifier] → [Report Agent]
                                → Unified Response
    """

    def __init__(self):
        print("🔧 Initializing Maintenance Wizard Agents...")
        self.rag_agent = RAGAgent()
        print("  ✅ RAG Agent (Gemini + ChromaDB) ready")
        self.anomaly_agent = AnomalyDetectionAgent()
        print("  ✅ Anomaly Detection Agent (Isolation Forest) ready")
        self.report_agent = ReportAgent()
        print("  ✅ Report Agent ready")

        # Lazy import to avoid circular
        self._rul_predictor = None
        self._risk_classifier = None

        # Session memory
        self.session_contexts: dict[str, dict] = {}
        print("🚀 Maintenance Wizard is online!\n")

    def _get_rul_predictor(self):
        if self._rul_predictor is None:
            from models.rul_model import RULPredictor
            data_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "sample_sensor_data.csv"
            )
            self._rul_predictor = RULPredictor()
            self._rul_predictor.load_or_train(data_path)
        return self._rul_predictor

    def _get_risk_classifier(self):
        if self._risk_classifier is None:
            from models.risk_classifier import RiskClassifier
            self._risk_classifier = RiskClassifier()
        return self._risk_classifier

    def _classify_intent(self, query: str) -> str:
        """Classify user query intent to route to appropriate agents."""
        query_lower = query.lower()
        
        if any(w in query_lower for w in ["analyze", "analyse", "check", "status", "reading", "sensor"]):
            return "analyze"
        elif any(w in query_lower for w in ["report", "generate", "summary", "document"]):
            return "report"
        elif any(w in query_lower for w in ["alert", "alarm", "warning", "anomaly", "fault", "error"]):
            return "diagnose"
        elif any(w in query_lower for w in ["predict", "remaining", "rul", "life", "when", "how long"]):
            return "predict"
        else:
            return "chat"

    def chat(
        self,
        query: str,
        session_id: str = "default",
        equipment_context: Optional[dict] = None,
    ) -> dict:
        """
        Handle a multi-turn conversational query.
        Uses RAG agent for contextual answers + optional sensor context.
        """
        # Update session context
        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = {
                "query_count": 0,
                "equipment_context": None,
                "last_query": None,
            }
        
        ctx = self.session_contexts[session_id]
        ctx["query_count"] += 1
        ctx["last_query"] = query
        if equipment_context:
            ctx["equipment_context"] = equipment_context

        # Use stored context if not provided fresh
        active_equipment = equipment_context or ctx.get("equipment_context")

        # If sensor data is present, augment with anomaly check
        anomaly_summary = None
        if active_equipment:
            anomaly_result = self.anomaly_agent.detect(active_equipment)
            if anomaly_result["is_anomaly"]:
                anomaly_summary = f"⚠️ Active anomaly detected on {anomaly_result['equipment_id']}: {anomaly_result['severity']} severity. Alerts: {'; '.join(anomaly_result['alerts'][:2])}"

        # Get RAG answer
        rag_response = self.rag_agent.answer(
            query=query,
            session_id=session_id,
            equipment_context=active_equipment,
        )

        # Prepend anomaly warning if relevant
        final_answer = rag_response["answer"]
        if anomaly_summary and "anomaly" in query.lower() or (anomaly_summary and active_equipment):
            final_answer = f"> **{anomaly_summary}**\n\n{final_answer}"

        return {
            "type": "chat",
            "answer": final_answer,
            "sources": rag_response.get("sources", []),
            "session_id": session_id,
            "query_count": ctx["query_count"],
            "timestamp": datetime.now().isoformat(),
            "success": rag_response.get("success", False),
        }

    def analyze_equipment(
        self,
        sensor_data: dict,
        session_id: str = "default",
        include_report: bool = False,
    ) -> dict:
        """
        Full pipeline analysis on equipment sensor data.
        Runs: Anomaly → Diagnosis → RUL → Risk → Optional Report
        """
        equipment_id = sensor_data.get("equipment_id", "UNKNOWN")
        
        # 1. Anomaly Detection
        anomaly_result = self.anomaly_agent.detect(sensor_data)
        
        # 2. Fault Diagnosis
        fault_codes = anomaly_result.get("inferred_fault_codes", [])
        diagnosis_result = diagnose_fault(fault_codes, sensor_data, equipment_id)
        
        # 3. RUL Prediction
        try:
            rul_result = self._get_rul_predictor().predict(sensor_data)
        except Exception as e:
            rul_result = {
                "rul_hours": 500,
                "rul_days": 20.8,
                "degradation_pct": 30.0,
                "confidence": "low",
                "trend": "stable",
                "error": str(e),
            }
        
        # 4. Risk Classification
        try:
            risk_result = self._get_risk_classifier().classify_risk(
                sensor_data, fault_codes, rul_result.get("rul_hours", 500)
            )
        except Exception as e:
            risk_result = {
                "risk_level": anomaly_result.get("severity", "LOW"),
                "risk_score": anomaly_result.get("anomaly_severity_score", 0),
                "factors": anomaly_result.get("alerts", []),
                "recommended_action": anomaly_result.get("recommendation", "Monitor equipment"),
                "intervention_urgency": "scheduled",
                "error": str(e),
            }

        # 5. Optional Report Generation
        report = None
        if include_report:
            report = self.report_agent.generate_report(
                equipment_id=equipment_id,
                anomaly_result=anomaly_result,
                diagnosis_result=diagnosis_result,
                rul_result=rul_result,
                risk_result=risk_result,
            )

        # 6. Build conversational summary
        summary = self._build_analysis_summary(
            equipment_id, anomaly_result, diagnosis_result, rul_result, risk_result
        )

        return {
            "type": "analysis",
            "equipment_id": equipment_id,
            "timestamp": datetime.now().isoformat(),
            "anomaly": anomaly_result,
            "diagnosis": diagnosis_result,
            "rul": rul_result,
            "risk": risk_result,
            "report": report,
            "summary": summary,
            "success": True,
        }

    def analyze_fleet(self, sensor_readings: list[dict]) -> dict:
        """Analyze all equipment in the fleet."""
        fleet_anomalies = self.anomaly_agent.get_fleet_summary(sensor_readings)
        
        # Get latest reading per equipment
        equipment_map = {}
        for reading in sensor_readings:
            eq_id = reading.get("equipment_id")
            if eq_id:
                equipment_map[eq_id] = reading

        # Analyze top critical equipment
        critical_analyses = []
        for reading in sensor_readings:
            anomaly = self.anomaly_agent.detect(reading)
            if anomaly["severity"] in ("CRITICAL", "HIGH"):
                try:
                    risk = self._get_risk_classifier().classify_risk(
                        reading, anomaly.get("inferred_fault_codes", []), 500
                    )
                except Exception:
                    risk = {"risk_level": anomaly["severity"], "risk_score": 70}
                critical_analyses.append({
                    "equipment_id": reading.get("equipment_id"),
                    "severity": anomaly["severity"],
                    "risk_level": risk.get("risk_level", anomaly["severity"]),
                    "alerts": anomaly.get("alerts", []),
                })

        # Sort by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "NORMAL": 3}
        critical_analyses.sort(key=lambda x: severity_order.get(x["severity"], 3))

        return {
            "type": "fleet_analysis",
            "timestamp": datetime.now().isoformat(),
            "fleet_summary": fleet_anomalies,
            "priority_equipment": critical_analyses[:5],
            "success": True,
        }

    def generate_report(
        self,
        equipment_id: str,
        sensor_data: Optional[dict] = None,
    ) -> dict:
        """Generate a standalone report for an equipment."""
        analysis = None
        if sensor_data:
            analysis = self.analyze_equipment(sensor_data, include_report=False)

        report = self.report_agent.generate_report(
            equipment_id=equipment_id,
            anomaly_result=analysis.get("anomaly") if analysis else None,
            diagnosis_result=analysis.get("diagnosis") if analysis else None,
            rul_result=analysis.get("rul") if analysis else None,
            risk_result=analysis.get("risk") if analysis else None,
        )
        return report

    def _build_analysis_summary(
        self,
        equipment_id: str,
        anomaly: dict,
        diagnosis: dict,
        rul: dict,
        risk: dict,
    ) -> str:
        severity = anomaly.get("severity", "NORMAL")
        primary_fault = diagnosis.get("primary_diagnosis", {})
        fault_name = primary_fault.get("fault_name", "No fault") if primary_fault else "No fault"
        rul_hours = rul.get("rul_hours", "N/A")
        risk_level = risk.get("risk_level", "LOW")

        emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "NORMAL": "🟢"}.get(severity, "🟢")

        lines = [
            f"{emoji} **{equipment_id}** — {risk_level} Risk",
            f"• Primary issue: {fault_name}",
            f"• Anomaly severity: {severity} (score: {anomaly.get('anomaly_severity_score', 0):.1f})",
            f"• Remaining useful life: {rul_hours} hours ({rul.get('rul_days', 'N/A')} days)",
            f"• Degradation: {rul.get('degradation_pct', 0):.1f}%",
        ]

        actions = diagnosis.get("consolidated_immediate_actions", [])
        if actions:
            lines.append(f"• Immediate action: {actions[0]}")

        return "\n".join(lines)

    def reset_session(self, session_id: str):
        """Clear all session state."""
        self.rag_agent.reset_session(session_id)
        if session_id in self.session_contexts:
            del self.session_contexts[session_id]
