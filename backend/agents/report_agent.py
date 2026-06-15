"""
Maintenance Wizard — Report Agent
Generates structured maintenance reports using Gemini LLM.
Combines all agent outputs into a human-readable report.
"""
import os
import sys
import json
from datetime import datetime
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

REPORT_PROMPT = """You are an expert industrial maintenance report writer for Tata Steel.
Generate a professional, structured maintenance report based on the provided data.
The report should be in markdown format with proper sections.
Be concise but comprehensive. Use technical language appropriate for maintenance engineers.
Include actionable recommendations with clear priority levels."""


class ReportAgent:
    """
    Generates structured maintenance reports by aggregating all agent outputs
    and using Gemini to produce a professional narrative.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key and api_key != "your_gemini_api_key_here":
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                system_instruction=REPORT_PROMPT,
            )
            self.llm_available = True
        else:
            self.llm_available = False

    def generate_report(
        self,
        equipment_id: str,
        anomaly_result: Optional[dict] = None,
        diagnosis_result: Optional[dict] = None,
        rul_result: Optional[dict] = None,
        risk_result: Optional[dict] = None,
        chat_context: Optional[str] = None,
    ) -> dict:
        """
        Generate a comprehensive maintenance report.
        Returns: {report_id, timestamp, report_markdown, report_json, summary}
        """
        report_id = f"RPT-{equipment_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        timestamp = datetime.now().isoformat()

        # Build structured data section
        structured_data = self._compile_structured_data(
            equipment_id, anomaly_result, diagnosis_result, rul_result, risk_result
        )

        # Generate narrative with LLM (or fallback to template)
        if self.llm_available:
            narrative = self._generate_llm_narrative(structured_data, chat_context)
        else:
            narrative = self._generate_template_narrative(structured_data)

        # Compose final report
        report_md = self._compose_markdown_report(
            report_id, timestamp, equipment_id, structured_data, narrative
        )

        return {
            "report_id": report_id,
            "timestamp": timestamp,
            "equipment_id": equipment_id,
            "report_markdown": report_md,
            "report_json": structured_data,
            "summary": self._extract_summary(structured_data, risk_result),
            "success": True,
        }

    def _compile_structured_data(
        self,
        equipment_id: str,
        anomaly: Optional[dict],
        diagnosis: Optional[dict],
        rul: Optional[dict],
        risk: Optional[dict],
    ) -> dict:
        data = {
            "equipment_id": equipment_id,
            "report_timestamp": datetime.now().isoformat(),
            "anomaly_detection": {},
            "fault_diagnosis": {},
            "rul_prediction": {},
            "risk_assessment": {},
        }

        if anomaly:
            data["anomaly_detection"] = {
                "is_anomaly": anomaly.get("is_anomaly", False),
                "severity": anomaly.get("severity", "NORMAL"),
                "anomaly_score": anomaly.get("anomaly_severity_score", 0),
                "active_alerts": anomaly.get("alerts", []),
                "fault_codes": anomaly.get("inferred_fault_codes", []),
                "sensor_readings": anomaly.get("sensor_snapshot", {}),
            }

        if diagnosis:
            primary = diagnosis.get("primary_diagnosis", {})
            data["fault_diagnosis"] = {
                "primary_fault": primary.get("fault_name", "No fault detected") if primary else "No fault detected",
                "probable_causes": primary.get("probable_causes", [])[:3] if primary else [],
                "immediate_actions": diagnosis.get("consolidated_immediate_actions", [])[:4],
                "maintenance_steps": primary.get("maintenance_steps", []) if primary else [],
                "spares_required": diagnosis.get("spares_required", []),
                "estimated_repair_hours": diagnosis.get("estimated_total_repair_hours", 0),
                "production_impact": diagnosis.get("production_impact", {}),
            }

        if rul:
            data["rul_prediction"] = {
                "rul_hours": rul.get("rul_hours", 0),
                "rul_days": rul.get("rul_days", 0),
                "degradation_pct": rul.get("degradation_pct", 0),
                "trend": rul.get("trend", "stable"),
                "confidence": rul.get("confidence", "medium"),
            }

        if risk:
            data["risk_assessment"] = {
                "risk_level": risk.get("risk_level", "LOW"),
                "risk_score": risk.get("risk_score", 0),
                "risk_factors": risk.get("factors", []),
                "recommended_action": risk.get("recommended_action", ""),
                "intervention_urgency": risk.get("intervention_urgency", "scheduled"),
            }

        return data

    def _generate_llm_narrative(self, data: dict, chat_context: Optional[str]) -> str:
        """Use Gemini to generate the narrative section of the report."""
        try:
            prompt = f"""Generate the FINDINGS AND RECOMMENDATIONS section of a maintenance report for equipment {data['equipment_id']}.

Data Summary:
- Anomaly Status: {data['anomaly_detection'].get('severity', 'NORMAL')}
- Primary Fault: {data['fault_diagnosis'].get('primary_fault', 'None')}
- Remaining Useful Life: {data['rul_prediction'].get('rul_hours', 'N/A')} hours
- Risk Level: {data['risk_assessment'].get('risk_level', 'LOW')}
- Top Alerts: {', '.join(data['anomaly_detection'].get('active_alerts', ['None'])[:3])}
- Probable Causes: {'; '.join(data['fault_diagnosis'].get('probable_causes', ['None'])[:2])}

{f'Engineer Query Context: {chat_context}' if chat_context else ''}

Write 2-3 paragraphs covering: (1) current equipment condition summary, (2) root cause analysis, (3) recommended maintenance strategy. Be technical and precise."""

            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return self._generate_template_narrative(data)

    def _generate_template_narrative(self, data: dict) -> str:
        """Fallback template-based narrative when LLM is not available."""
        severity = data["anomaly_detection"].get("severity", "NORMAL")
        primary_fault = data["fault_diagnosis"].get("primary_fault", "No specific fault")
        rul_hours = data["rul_prediction"].get("rul_hours", "N/A")
        risk_level = data["risk_assessment"].get("risk_level", "LOW")

        return f"""**Equipment Condition:** The equipment is currently showing {severity} status based on real-time sensor analysis. {"An anomaly has been detected requiring attention." if data["anomaly_detection"].get("is_anomaly") else "No anomalies detected in current readings."}

**Root Cause Analysis:** {primary_fault} has been identified as the primary concern. {"The sensor data indicates " + ", ".join(data["fault_diagnosis"].get("probable_causes", ["no specific causes identified"])[:2]) + "." if data["fault_diagnosis"].get("probable_causes") else "No fault pattern matched current readings."}

**Maintenance Strategy:** Based on the {risk_level} risk classification and estimated remaining useful life of {rul_hours} hours, {data["risk_assessment"].get("recommended_action", "standard monitoring is recommended")}. Priority spares to procure: {", ".join(data["fault_diagnosis"].get("spares_required", ["N/A"])[:3])}."""

    def _compose_markdown_report(
        self,
        report_id: str,
        timestamp: str,
        equipment_id: str,
        data: dict,
        narrative: str,
    ) -> str:
        risk_level = data["risk_assessment"].get("risk_level", "LOW")
        risk_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk_level, "🟢")

        alerts = data["anomaly_detection"].get("active_alerts", [])
        alerts_str = "\n".join(f"- {a}" for a in alerts) if alerts else "- No active alerts"

        causes = data["fault_diagnosis"].get("probable_causes", [])
        causes_str = "\n".join(f"- {c}" for c in causes[:3]) if causes else "- No fault indicators detected"

        actions = data["fault_diagnosis"].get("immediate_actions", [])
        actions_str = "\n".join(f"- {a}" for a in actions[:4]) if actions else "- Continue standard monitoring"

        steps = data["fault_diagnosis"].get("maintenance_steps", [])
        steps_str = "\n".join(f"{s}" for s in steps[:6]) if steps else "- No corrective maintenance required"

        spares = data["fault_diagnosis"].get("spares_required", [])
        spares_str = "\n".join(f"- {s}" for s in spares[:5]) if spares else "- No spares required"

        sensors = data["anomaly_detection"].get("sensor_readings", {})
        sensors_str = "\n".join(
            f"| {k.replace('_', ' ').title()} | {v:.2f} |" for k, v in sensors.items() if v is not None
        ) if sensors else "| No data | N/A |"

        rul = data["rul_prediction"]
        risk = data["risk_assessment"]

        return f"""# 🏭 Maintenance Report — {equipment_id}
**Report ID:** `{report_id}`  
**Generated:** {datetime.fromisoformat(timestamp).strftime("%d %b %Y, %H:%M:%S")}  
**Status:** {risk_emoji} **{risk_level} RISK**

---

## 1. Executive Summary

| Parameter | Value |
|-----------|-------|
| Equipment ID | {equipment_id} |
| Anomaly Detected | {"⚠️ YES" if data["anomaly_detection"].get("is_anomaly") else "✅ NO"} |
| Primary Fault | {data["fault_diagnosis"].get("primary_fault", "None")} |
| Risk Level | {risk_emoji} {risk_level} |
| Risk Score | {risk.get("risk_score", 0):.1f} / 100 |
| Remaining Useful Life | {rul.get("rul_hours", "N/A")} hours ({rul.get("rul_days", "N/A")} days) |
| Degradation | {rul.get("degradation_pct", 0):.1f}% |
| Intervention Required | {risk.get("intervention_urgency", "scheduled").upper()} |

---

## 2. Active Alerts

{alerts_str}

---

## 3. Sensor Readings Snapshot

| Sensor | Reading |
|--------|---------|
{sensors_str}

---

## 4. Findings & Recommendations

{narrative}

---

## 5. Root Cause Analysis

**Probable Causes:**

{causes_str}

---

## 6. Immediate Actions Required

{actions_str}

---

## 7. Maintenance Procedure

{steps_str}

---

## 8. Spare Parts Required

{spares_str}

**Estimated Repair Time:** {data["fault_diagnosis"].get("estimated_repair_hours", 0)} hours  
**Production Impact:** {data["fault_diagnosis"].get("production_impact", {}).get("level", "LOW")} — {data["fault_diagnosis"].get("production_impact", {}).get("description", "Minimal impact")}

---

## 9. Long-Term Recommendations

- Implement vibration monitoring every 15 minutes for next 7 days
- Conduct oil analysis sampling after maintenance
- Review maintenance history for recurring patterns
- Update equipment digital logbook with this incident

---

*Report generated by Maintenance Wizard AI — Tata Steel Agentic AI System*  
*Model: Gemini 1.5 Flash + Local ML (Isolation Forest + RandomForest)*
"""

    def _extract_summary(self, data: dict, risk: Optional[dict]) -> str:
        risk_level = risk.get("risk_level", "LOW") if risk else "LOW"
        primary = data["fault_diagnosis"].get("primary_fault", "No fault")
        rul_hours = data["rul_prediction"].get("rul_hours", "N/A")
        return f"{risk_level} risk | {primary} | RUL: {rul_hours}h"
