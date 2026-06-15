"""
generate_data.py
----------------
Generates synthetic maintenance data for the Tata Steel Maintenance Wizard project.
Produces two CSV files:
  1. sample_sensor_data.csv  – 600 rows of sensor readings with ~90 anomalies
  2. equipment_logs.csv      – 100 rows of maintenance log entries

Run with:  python generate_data.py
"""

import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ── reproducibility ────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── output directory (same folder as this script) ──────────────────────────────
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==============================================================================
# FILE 1 – sample_sensor_data.csv
# ==============================================================================

EQUIPMENT = {
    "BF-01":   "BLAST_FURNACE",
    "BF-02":   "BLAST_FURNACE",
    "RM-01":   "ROLLING_MILL",
    "RM-02":   "ROLLING_MILL",
    "PUMP-01": "PUMP",
    "PUMP-02": "PUMP",
    "CONV-01": "CONVEYOR",
    "CONV-02": "CONVEYOR",
    "COMP-01": "COMPRESSOR",
    "COMP-02": "COMPRESSOR",
}

FAULT_CODES = [
    "E001-BEARING_WEAR",
    "E002-OVERHEAT",
    "E003-PRESSURE_LOSS",
    "E004-OVERCURRENT",
    "E005-LOW_OIL",
    "E006-VIBRATION_HIGH",
]

TOTAL_ROWS   = 600
ANOMALY_ROWS = 90   # ~15 %
NORMAL_ROWS  = TOTAL_ROWS - ANOMALY_ROWS

# ── time axis: past 30 days at regular intervals ───────────────────────────────
end_time   = datetime(2026, 6, 15, 10, 0, 0)
start_time = end_time - timedelta(days=30)
timestamps = [
    start_time + timedelta(seconds=i * (30 * 24 * 3600) / (TOTAL_ROWS - 1))
    for i in range(TOTAL_ROWS)
]

# ── assign equipment IDs round-robin across all rows ───────────────────────────
eq_ids = list(EQUIPMENT.keys())
equipment_id_col = [eq_ids[i % len(eq_ids)] for i in range(TOTAL_ROWS)]
random.shuffle(equipment_id_col)

# ── build rows ─────────────────────────────────────────────────────────────────
anomaly_indices = sorted(random.sample(range(TOTAL_ROWS), ANOMALY_ROWS))
anomaly_set     = set(anomaly_indices)

rows = []
for idx in range(TOTAL_ROWS):
    eq   = equipment_id_col[idx]
    ts   = timestamps[idx]
    anom = idx in anomaly_set

    if anom:
        vibration   = round(random.uniform(4.5, 8.5),  2)
        temperature = round(random.uniform(100.0, 140.0), 1)
        # pressure: either very low or very high
        pressure    = round(
            random.uniform(0.3, 1.2) if random.random() < 0.5 else random.uniform(10.1, 14.0),
            2,
        )
        current     = round(random.uniform(220.0, 280.0), 1)
        rpm         = round(random.uniform(500.0, 3000.0), 0)
        oil_level   = round(random.uniform(5.0, 20.0), 1)
        noise       = round(random.uniform(78.0, 105.0), 1)
        fault_code  = random.choice(FAULT_CODES)
        is_anomaly  = 1
    else:
        vibration   = round(random.uniform(0.5, 3.0),  2)
        temperature = round(random.uniform(40.0, 90.0), 1)
        pressure    = round(random.uniform(2.0, 8.0),  2)
        current     = round(random.uniform(50.0, 200.0), 1)
        rpm         = round(random.uniform(500.0, 3000.0), 0)
        oil_level   = round(random.uniform(65.0, 100.0), 1)
        noise       = round(random.uniform(40.0, 75.0), 1)
        fault_code  = None
        is_anomaly  = 0

    rows.append(
        {
            "timestamp":       ts.strftime("%Y-%m-%d %H:%M:%S"),
            "equipment_id":    eq,
            "equipment_type":  EQUIPMENT[eq],
            "vibration_mm_s":  vibration,
            "temperature_c":   temperature,
            "pressure_bar":    pressure,
            "current_amp":     current,
            "rpm":             rpm,
            "oil_level_pct":   oil_level,
            "noise_db":        noise,
            "fault_code":      fault_code,
            "is_anomaly":      is_anomaly,
        }
    )

sensor_df = pd.DataFrame(rows)
sensor_path = os.path.join(OUT_DIR, "sample_sensor_data.csv")
sensor_df.to_csv(sensor_path, index=False)
print(f"[OK] sample_sensor_data.csv  -> {len(sensor_df)} rows saved to {sensor_path}")

# ==============================================================================
# FILE 2 – equipment_logs.csv
# ==============================================================================

LOG_ROWS = 100

FAULT_DESCRIPTIONS = [
    "Excessive vibration detected on main drive bearing - resonance frequency 48 Hz",
    "Overheating of motor winding; insulation resistance dropped below 50 MOhm",
    "Hydraulic pressure loss in roll gap control circuit - suspected valve seat wear",
    "Tuyere blockage identified in zone C; blast pressure spike of 0.8 bar observed",
    "Cooling stave outlet temperature rose 12 degC above baseline during peak load",
    "Conveyor belt mis-tracking causing edge wear on drive pulley",
    "Mechanical seal leakage on slurry pump suction side; bearing housing wet",
    "Compressor oil separator element clogged; oil carryover >5 ppm in discharge",
    "Roll bearing temperature reached 88 degC - lubrication interval overdue",
    "Belt tear (150 mm longitudinal) detected at loading chute - stone impact",
    "Scaffold formation in blast furnace upper shaft - burden distribution irregular",
    "Refractory erosion at tap hole - clay gun inconsistency noted",
    "VFD fault on rolling mill motor - DC bus overvoltage during deceleration",
    "Impeller wear - pump flow reduced 18% at rated head",
    "Idler seizure at conveyor head-end transfer point - smoke detected",
    "Oil level low on compressor unit; external micro-leak at fitting",
    "Pressure valve chattering on pneumatic system - set point drift",
    "Belt slip 7% during wet weather loading; tension inadequate",
    "Stave cooling water flow reduced - scaling in water circuit",
    "Motor current unbalance >5% - rotor bar cracked on phase 2",
]

MAINTENANCE_ACTIONS = [
    "Bearing replacement",
    "Thermal flush and cooling system service",
    "Pressure valve adjustment",
    "Electrical panel inspection",
    "Oil change and seal replacement",
    "Belt tension adjustment",
    "Motor winding test",
    "Sensor calibration and replacement",
    "Full preventive maintenance",
]

PARTS_REPLACED = [
    "SKF 6310-2RS deep groove bearing",
    "Mechanical seal kit (John Crane T21)",
    "Hydraulic pressure relief valve (Parker D1VW)",
    "Compressor oil separator element",
    "Conveyor belt idler (5-roll garland set)",
    "Pump impeller - hard chrome alloy 310mm",
    "VFD IGBTs and gate-drive board",
    "Thermocouple sensor (K-type, 6mm)",
    "Tuyere copper nose assembly",
    "Oil seal and O-ring kit",
    "Cooling stave hose connection",
    "Belt fastener repair strip (Flexco R5)",
    "Motor terminal block and crimps",
    "Pressure transmitter (Endress+Hauser PMP71)",
    "Refractory ramming mass (20 kg)",
    "Gearbox oil seal set",
    "Vibration sensor (4-20mA, ICP)",
    "Drive pulley lagging (12mm rubber)",
    "Filter element (hydraulic, 10 micron)",
    "None - adjusted existing components",
]

TECHNICIANS = [
    "Rajan Kumar",
    "Suresh Patel",
    "Amit Singh",
    "Priya Sharma",
    "Dinesh Yadav",
    "Manoj Tiwari",
    "Kavita Nair",
    "Rakesh Gupta",
]

# severity distribution: Low 30%, Medium 35%, High 25%, Critical 10%
SEVERITY_CHOICES = (
    ["Low"] * 30
    + ["Medium"] * 35
    + ["High"] * 25
    + ["Critical"] * 10
)

# resolution distribution: Resolved 70%, In-Progress 20%, Pending 10%
RESOLUTION_CHOICES = (
    ["Resolved"] * 70
    + ["In-Progress"] * 20
    + ["Pending"] * 10
)

COST_RANGES = {
    "Low":      (8_000,   60_000),
    "Medium":   (60_000,  200_000),
    "High":     (200_000, 450_000),
    "Critical": (450_000, 600_000),
}

DELAY_RANGES = {
    "Low":      (0.5,  4.0),
    "Medium":   (2.0,  12.0),
    "High":     (8.0,  24.0),
    "Critical": (12.0, 48.0),
}

log_rows = []
log_end   = datetime(2026, 6, 15, 10, 0, 0)
log_start = log_end - timedelta(days=180)   # 6 months of history

for i in range(LOG_ROWS):
    log_ts   = log_start + timedelta(
        seconds=random.randint(0, int((log_end - log_start).total_seconds()))
    )
    severity   = random.choice(SEVERITY_CHOICES)
    resolution = random.choice(RESOLUTION_CHOICES)
    cost_min, cost_max   = COST_RANGES[severity]
    delay_min, delay_max = DELAY_RANGES[severity]

    log_rows.append(
        {
            "log_id":              f"LOG-{1000 + i + 1}",
            "timestamp":           log_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "equipment_id":        random.choice(eq_ids),
            "fault_description":   random.choice(FAULT_DESCRIPTIONS),
            "delay_hours":         round(random.uniform(delay_min, delay_max), 1),
            "severity":            severity,
            "maintenance_action":  random.choice(MAINTENANCE_ACTIONS),
            "parts_replaced":      random.choice(PARTS_REPLACED),
            "technician_name":     random.choice(TECHNICIANS),
            "resolution_status":   resolution,
            "estimated_cost_inr":  random.randint(cost_min, cost_max),
        }
    )

logs_df = pd.DataFrame(log_rows).sort_values("timestamp").reset_index(drop=True)
logs_path = os.path.join(OUT_DIR, "equipment_logs.csv")
logs_df.to_csv(logs_path, index=False)
print(f"[OK] equipment_logs.csv      -> {len(logs_df)} rows saved to {logs_path}")
