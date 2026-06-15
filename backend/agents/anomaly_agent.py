"""
Maintenance Wizard — Anomaly Detection Agent
Uses Isolation Forest (unsupervised ML) to detect equipment anomalies
from real-time sensor readings. Runs 100% locally, no API needed.
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "saved")
ANOMALY_MODEL_PATH = os.path.join(MODEL_DIR, "anomaly_model.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "anomaly_scaler.pkl")

SENSOR_FEATURES = [
    "vibration_mm_s",
    "temperature_c",
    "pressure_bar",
    "current_amp",
    "rpm",
    "oil_level_pct",
    "noise_db",
]

# Normal operating thresholds per equipment type
THRESHOLDS = {
    "BF": {  # Blast Furnace
        "temperature_c": {"warn": 100, "critical": 130},
        "pressure_bar": {"warn": 9, "critical": 12},
        "vibration_mm_s": {"warn": 3.5, "critical": 6.0},
        "current_amp": {"warn": 180, "critical": 230},
        "oil_level_pct": {"warn": 35, "critical": 20},
    },
    "RM": {  # Rolling Mill
        "temperature_c": {"warn": 95, "critical": 120},
        "pressure_bar": {"warn": 10, "critical": 14},
        "vibration_mm_s": {"warn": 4.0, "critical": 7.0},
        "current_amp": {"warn": 190, "critical": 240},
        "oil_level_pct": {"warn": 30, "critical": 15},
    },
    "PUMP": {  # Pump
        "temperature_c": {"warn": 80, "critical": 105},
        "pressure_bar": {"warn": 8, "critical": 11},
        "vibration_mm_s": {"warn": 3.0, "critical": 5.5},
        "current_amp": {"warn": 160, "critical": 200},
        "oil_level_pct": {"warn": 40, "critical": 25},
    },
    "CONV": {  # Conveyor
        "temperature_c": {"warn": 70, "critical": 90},
        "vibration_mm_s": {"warn": 3.0, "critical": 5.0},
        "current_amp": {"warn": 140, "critical": 180},
        "oil_level_pct": {"warn": 40, "critical": 25},
    },
    "COMP": {  # Compressor
        "temperature_c": {"warn": 85, "critical": 110},
        "pressure_bar": {"warn": 11, "critical": 15},
        "vibration_mm_s": {"warn": 3.5, "critical": 6.0},
        "current_amp": {"warn": 170, "critical": 220},
        "oil_level_pct": {"warn": 35, "critical": 20},
    },
}

FAULT_CODE_MAP = {
    "E001-BEARING_WEAR": {
        "name": "Bearing Wear",
        "description": "Abnormal vibration pattern indicating bearing degradation",
        "primary_sensor": "vibration_mm_s",
    },
    "E002-OVERHEAT": {
        "name": "Overheating",
        "description": "Equipment temperature exceeding safe operating limits",
        "primary_sensor": "temperature_c",
    },
    "E003-PRESSURE_LOSS": {
        "name": "Pressure Loss",
        "description": "System pressure below minimum operational threshold",
        "primary_sensor": "pressure_bar",
    },
    "E004-OVERCURRENT": {
        "name": "Overcurrent",
        "description": "Electrical current draw above rated capacity",
        "primary_sensor": "current_amp",
    },
    "E005-LOW_OIL": {
        "name": "Low Oil Level",
        "description": "Lubricant level critically low — risk of seizure",
        "primary_sensor": "oil_level_pct",
    },
    "E006-VIBRATION_HIGH": {
        "name": "High Vibration",
        "description": "Excessive mechanical vibration — possible imbalance or misalignment",
        "primary_sensor": "vibration_mm_s",
    },
}


class AnomalyDetectionAgent:
    """
    Detects equipment anomalies using:
    1. Isolation Forest (ML-based, unsupervised)
    2. Rule-based threshold checks per equipment type
    """

    def __init__(self):
        os.makedirs(MODEL_DIR, exist_ok=True)
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self._load_or_train()

    def _get_equipment_prefix(self, equipment_id: str) -> str:
        for prefix in THRESHOLDS:
            if equipment_id.upper().startswith(prefix):
                return prefix
        return "PUMP"  # default

    def _train_model(self, df: Optional[pd.DataFrame] = None):
        """Train Isolation Forest on normal sensor data."""
        if df is None:
            # Generate synthetic normal data for training
            np.random.seed(42)
            n = 2000
            df = pd.DataFrame({
                "vibration_mm_s": np.random.normal(1.8, 0.6, n).clip(0.3, 3.5),
                "temperature_c": np.random.normal(65, 15, n).clip(30, 100),
                "pressure_bar": np.random.normal(5.0, 1.2, n).clip(1.5, 9.0),
                "current_amp": np.random.normal(120, 30, n).clip(40, 190),
                "rpm": np.random.normal(1500, 400, n).clip(400, 2800),
                "oil_level_pct": np.random.normal(75, 12, n).clip(30, 100),
                "noise_db": np.random.normal(60, 8, n).clip(35, 80),
            })

        X = df[SENSOR_FEATURES].fillna(df[SENSOR_FEATURES].mean())
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        self.model = IsolationForest(
            n_estimators=200,
            contamination=0.12,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_scaled)
        joblib.dump(self.model, ANOMALY_MODEL_PATH)
        joblib.dump(self.scaler, SCALER_PATH)

    def _load_or_train(self):
        """Load existing model or train a new one."""
        if os.path.exists(ANOMALY_MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                self.model = joblib.load(ANOMALY_MODEL_PATH)
                self.scaler = joblib.load(SCALER_PATH)
                return
            except Exception:
                pass
        self._train_model()

    def detect(self, sensor_data: dict) -> dict:
        """
        Run anomaly detection on a single sensor reading.
        Returns comprehensive anomaly report.
        """
        equipment_id = sensor_data.get("equipment_id", "UNKNOWN")
        eq_prefix = self._get_equipment_prefix(equipment_id)
        thresholds = THRESHOLDS.get(eq_prefix, THRESHOLDS["PUMP"])

        # --- 1. ML-based anomaly score ---
        feature_values = [
            float(sensor_data.get(f, 0)) for f in SENSOR_FEATURES
        ]
        X = np.array(feature_values).reshape(1, -1)
        X_scaled = self.scaler.transform(X)
        ml_score = self.model.score_samples(X_scaled)[0]  # more negative = more anomalous
        is_ml_anomaly = self.model.predict(X_scaled)[0] == -1

        # Normalize score to 0-100 (anomaly severity)
        anomaly_severity = max(0, min(100, (-ml_score + 0.1) * 200))

        # --- 2. Rule-based threshold checks ---
        threshold_violations = []
        alerts = []

        for sensor, limits in thresholds.items():
            val = sensor_data.get(sensor)
            if val is None:
                continue
            val = float(val)
            if "critical" in limits and val >= limits["critical"]:
                threshold_violations.append({
                    "sensor": sensor,
                    "value": val,
                    "threshold": limits["critical"],
                    "level": "CRITICAL",
                })
                alerts.append(f"⚠️ CRITICAL: {sensor} = {val:.1f} (limit: {limits['critical']})")
            elif "warn" in limits and val >= limits["warn"]:
                threshold_violations.append({
                    "sensor": sensor,
                    "value": val,
                    "threshold": limits["warn"],
                    "level": "WARNING",
                })
                alerts.append(f"⚡ WARNING: {sensor} = {val:.1f} (limit: {limits['warn']})")

        # Special case: low pressure or low oil
        pressure = sensor_data.get("pressure_bar")
        if pressure is not None and float(pressure) < 1.0:
            threshold_violations.append({
                "sensor": "pressure_bar",
                "value": float(pressure),
                "threshold": 1.0,
                "level": "CRITICAL",
            })
            alerts.append(f"⚠️ CRITICAL: pressure_bar = {float(pressure):.2f} (min: 1.0 bar)")

        oil = sensor_data.get("oil_level_pct")
        if oil is not None and float(oil) < 20:
            threshold_violations.append({
                "sensor": "oil_level_pct",
                "value": float(oil),
                "threshold": 20,
                "level": "CRITICAL",
            })
            alerts.append(f"⚠️ CRITICAL: oil_level_pct = {float(oil):.1f}% (min: 20%)")

        # --- 3. Fault code inference ---
        inferred_faults = []
        vib = float(sensor_data.get("vibration_mm_s", 0))
        temp = float(sensor_data.get("temperature_c", 0))
        pres = float(sensor_data.get("pressure_bar", 999))
        curr = float(sensor_data.get("current_amp", 0))
        oil_lvl = float(sensor_data.get("oil_level_pct", 100))

        if vib > 4.0:
            inferred_faults.append("E001-BEARING_WEAR" if vib > 5.5 else "E006-VIBRATION_HIGH")
        if temp > 100:
            inferred_faults.append("E002-OVERHEAT")
        if pres < 1.5:
            inferred_faults.append("E003-PRESSURE_LOSS")
        if curr > 200:
            inferred_faults.append("E004-OVERCURRENT")
        if oil_lvl < 25:
            inferred_faults.append("E005-LOW_OIL")

        # Also include provided fault code
        provided_fault = sensor_data.get("fault_code")
        if provided_fault and provided_fault != "None" and provided_fault not in inferred_faults:
            inferred_faults.insert(0, provided_fault)

        fault_details = [
            {**FAULT_CODE_MAP[f], "code": f}
            for f in inferred_faults
            if f in FAULT_CODE_MAP
        ]

        # --- 4. Combined is_anomaly flag ---
        is_anomaly = is_ml_anomaly or len(threshold_violations) > 0

        # --- 5. Severity classification ---
        has_critical = any(v["level"] == "CRITICAL" for v in threshold_violations)
        has_warning = any(v["level"] == "WARNING" for v in threshold_violations)

        if has_critical or (is_ml_anomaly and anomaly_severity > 70):
            severity = "CRITICAL"
        elif has_warning or (is_ml_anomaly and anomaly_severity > 40):
            severity = "HIGH"
        elif is_anomaly:
            severity = "MEDIUM"
        else:
            severity = "NORMAL"

        return {
            "equipment_id": equipment_id,
            "equipment_type": sensor_data.get("equipment_type", eq_prefix),
            "is_anomaly": is_anomaly,
            "severity": severity,
            "anomaly_severity_score": round(anomaly_severity, 2),
            "ml_anomaly_detected": is_ml_anomaly,
            "threshold_violations": threshold_violations,
            "alerts": alerts,
            "inferred_fault_codes": inferred_faults,
            "fault_details": fault_details,
            "sensor_snapshot": {
                k: sensor_data.get(k) for k in SENSOR_FEATURES
            },
            "recommendation": self._get_recommendation(severity, inferred_faults),
        }

    def _get_recommendation(self, severity: str, fault_codes: list) -> str:
        recs = {
            "CRITICAL": "🛑 IMMEDIATE ACTION REQUIRED: Initiate emergency shutdown procedure. Alert maintenance supervisor. Do not operate until inspected.",
            "HIGH": "⚠️ URGENT: Schedule maintenance within 24 hours. Reduce operational load. Monitor continuously.",
            "MEDIUM": "📋 Schedule inspection within 72 hours. Increase monitoring frequency to every 15 minutes.",
            "NORMAL": "✅ Equipment operating within normal parameters. Continue standard monitoring schedule.",
        }
        base = recs.get(severity, recs["NORMAL"])
        if "E005-LOW_OIL" in fault_codes:
            base += " Prioritize oil refill immediately."
        if "E002-OVERHEAT" in fault_codes:
            base += " Check cooling system and ventilation."
        return base

    def detect_batch(self, sensor_readings: list[dict]) -> list[dict]:
        """Run anomaly detection on multiple readings."""
        return [self.detect(r) for r in sensor_readings]

    def get_fleet_summary(self, sensor_readings: list[dict]) -> dict:
        """Summarize anomaly status across all equipment."""
        results = self.detect_batch(sensor_readings)
        summary = {
            "total_equipment": len(results),
            "critical": sum(1 for r in results if r["severity"] == "CRITICAL"),
            "high": sum(1 for r in results if r["severity"] == "HIGH"),
            "medium": sum(1 for r in results if r["severity"] == "MEDIUM"),
            "normal": sum(1 for r in results if r["severity"] == "NORMAL"),
            "anomaly_rate_pct": round(
                100 * sum(1 for r in results if r["is_anomaly"]) / max(len(results), 1), 1
            ),
            "details": results,
        }
        return summary
