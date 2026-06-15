"""
Maintenance Wizard — Diagnostic Agent
Performs fault diagnosis using rule-based pattern matching + LLM reasoning.
Maps fault codes and sensor patterns to probable root causes.
"""
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ─── Fault Knowledge Base ────────────────────────────────────────────────────

FAULT_DIAGNOSIS_KB = {
    "E001-BEARING_WEAR": {
        "name": "Bearing Wear / Failure",
        "probable_causes": [
            "Insufficient lubrication leading to metal-on-metal contact",
            "Contamination of bearing grease by dust or moisture",
            "Overloading beyond rated capacity",
            "Improper bearing installation or misalignment",
            "End-of-life fatigue (exceeding design life cycles)",
        ],
        "root_cause_indicators": {
            "vibration_mm_s > 4.0": "Stage 1 bearing wear — inner/outer race defect frequency detectable",
            "vibration_mm_s > 6.0": "Stage 3 bearing wear — imminent failure, replace immediately",
            "temperature_c > 80": "Friction heat from inadequate lubrication",
            "noise_db > 75": "Metal fatigue cracking in bearing races",
        },
        "immediate_actions": [
            "Reduce equipment load to minimum",
            "Check and replenish bearing lubrication immediately",
            "Isolate equipment if vibration > 6 mm/s",
            "Request vibration spectrum analysis from maintenance team",
        ],
        "maintenance_steps": [
            "1. Shutdown equipment following SOP-SHUTDOWN-001",
            "2. Lock out / Tag out (LOTO) the equipment",
            "3. Remove bearing housing cover and inspect bearing condition",
            "4. Clean bearing housing and check for contamination",
            "5. Replace bearing if pitting, spalling, or discoloration found",
            "6. Apply correct grade of lubricant (check OEM manual)",
            "7. Check shaft alignment after bearing replacement",
            "8. Run equipment at 25% load for 30 min and monitor vibration",
        ],
        "spares_needed": ["SKF 6310 Deep Groove Ball Bearing", "Shell Gadus S2 V220 grease", "Bearing housing gasket"],
        "typical_repair_time_hours": 4,
        "safety_note": "Ensure LOTO procedure is completed. Hot bearings may cause burns — allow 30 min cooling.",
    },
    "E002-OVERHEAT": {
        "name": "Equipment Overheating",
        "probable_causes": [
            "Cooling system failure or blocked coolant flow",
            "Inadequate ventilation around equipment",
            "Overloading — operating beyond rated duty cycle",
            "High ambient temperature in plant area",
            "Coolant pump failure",
        ],
        "root_cause_indicators": {
            "temperature_c > 100": "Cooling system partially compromised",
            "temperature_c > 130": "Cooling system failure — risk of fire",
            "current_amp elevated": "Motor overloading causing resistive heating",
        },
        "immediate_actions": [
            "Reduce load or shutdown if temperature > 120°C",
            "Check cooling water flow rate",
            "Ensure ventilation fans are operational",
            "Notify safety officer if temperature > 130°C",
        ],
        "maintenance_steps": [
            "1. Shutdown and LOTO the equipment",
            "2. Allow cooling to <40°C before touching internals",
            "3. Inspect coolant lines for blockages or leaks",
            "4. Clean heat exchanger fins with compressed air",
            "5. Check coolant pump pressure and flow",
            "6. Verify temperature sensor accuracy (calibrate if needed)",
            "7. Check load profile — consult with process engineer if overloading",
        ],
        "spares_needed": ["Coolant pump impeller", "Heat exchanger gasket", "Temperature sensor PT100"],
        "typical_repair_time_hours": 3,
        "safety_note": "Fire risk if temperature > 130°C. Have fire extinguisher ready. Use PPE including heat-resistant gloves.",
    },
    "E003-PRESSURE_LOSS": {
        "name": "System Pressure Loss",
        "probable_causes": [
            "Hydraulic/pneumatic line leak or rupture",
            "Pressure relief valve stuck open",
            "Pump wear reducing output pressure",
            "Seal failure on cylinder or actuator",
            "Filter clogging causing pressure drop",
        ],
        "immediate_actions": [
            "Check system for visible leaks",
            "Verify pressure relief valve setting",
            "Check pump inlet conditions",
            "Isolate section if major leak detected",
        ],
        "maintenance_steps": [
            "1. Depressurize system completely before inspection",
            "2. Inspect all hose connections, fittings, and joints for leaks",
            "3. Check pressure relief valve with calibrated gauge",
            "4. Inspect pump for wear — check pressure vs flow curve",
            "5. Replace seals if cylinder drift observed",
            "6. Clean or replace hydraulic filters",
        ],
        "spares_needed": ["Hydraulic seal kit", "Pressure relief valve", "Filter element"],
        "typical_repair_time_hours": 2,
        "safety_note": "Never open pressurized lines. Depressurize fully before maintenance.",
    },
    "E004-OVERCURRENT": {
        "name": "Motor Overcurrent",
        "probable_causes": [
            "Mechanical overload on driven equipment",
            "Phase imbalance in power supply",
            "Motor winding degradation (insulation failure)",
            "Blocked or jammed driven mechanism",
            "Single-phasing due to blown fuse",
        ],
        "immediate_actions": [
            "Check current on all three phases with clamp meter",
            "Inspect for mechanical jams in driven equipment",
            "Verify supply voltage levels",
            "Check overload relay setting",
        ],
        "maintenance_steps": [
            "1. Measure current draw on all phases",
            "2. Check motor insulation resistance with megohmmeter (>100 MΩ acceptable)",
            "3. Inspect driven equipment for blockages",
            "4. Check and tighten all electrical connections",
            "5. Verify VFD parameters if variable speed drive used",
            "6. Test motor no-load current vs rated value",
        ],
        "spares_needed": ["Overload relay", "Motor contactor", "Phase failure relay"],
        "typical_repair_time_hours": 3,
        "safety_note": "Electrical work — qualified electrician only. Lock out main isolator before any work.",
    },
    "E005-LOW_OIL": {
        "name": "Low Oil / Lubricant Level",
        "probable_causes": [
            "Oil leak from seals or drain plug",
            "Consumption above normal due to seal degradation",
            "Scheduled oil change overdue",
            "External contamination causing oil loss",
        ],
        "immediate_actions": [
            "Refill oil to recommended level immediately",
            "Inspect for visible leaks around seals, gaskets, drain plugs",
            "Reduce load until oil is replenished",
        ],
        "maintenance_steps": [
            "1. Stop equipment and allow to cool",
            "2. Identify and fix any oil leak source",
            "3. Drain contaminated oil if necessary",
            "4. Refill with correct grade oil (refer to equipment manual)",
            "5. Run equipment and check for continued leaks",
            "6. Sample oil for particle analysis if history of leaks",
        ],
        "spares_needed": ["Equipment-specific oil grade", "Oil seal kit", "Drain plug washer"],
        "typical_repair_time_hours": 1,
        "safety_note": "Oil spills create slip hazard. Use oil-absorbent mats. Dispose of waste oil per plant SOP.",
    },
    "E006-VIBRATION_HIGH": {
        "name": "High Vibration / Imbalance",
        "probable_causes": [
            "Rotor imbalance due to material buildup or damage",
            "Shaft misalignment after maintenance",
            "Loose foundation bolts or mounting",
            "Resonance with structure natural frequency",
            "Early-stage bearing wear (distinguish from E001)",
        ],
        "immediate_actions": [
            "Check foundation bolts for looseness",
            "Inspect for visible material buildup on rotating parts",
            "Reduce speed if possible",
        ],
        "maintenance_steps": [
            "1. Perform vibration spectrum analysis to identify frequency",
            "2. Check and tighten all foundation and mounting bolts",
            "3. Perform dynamic balancing if rotor imbalance confirmed",
            "4. Check shaft alignment using laser alignment tool",
            "5. Inspect for structural resonance — check operating speed vs critical speed",
        ],
        "spares_needed": ["Balance weights", "Anti-vibration mounts", "Coupling insert"],
        "typical_repair_time_hours": 5,
        "safety_note": "High vibration can cause equipment to walk off foundation. Barricade area if critical.",
    },
}


def diagnose_fault(
    fault_codes: list,
    sensor_data: dict,
    equipment_id: str,
) -> dict:
    """
    Perform rule-based fault diagnosis.
    Returns structured diagnosis with root causes, actions, and steps.
    """
    if not fault_codes:
        # No fault codes — check sensors for subtle issues
        fault_codes = _infer_faults_from_sensors(sensor_data)

    diagnoses = []
    all_immediate_actions = []
    all_spares = []
    total_repair_hours = 0

    for code in fault_codes:
        if code in FAULT_DIAGNOSIS_KB:
            kb = FAULT_DIAGNOSIS_KB[code]
            diagnosis = {
                "fault_code": code,
                "fault_name": kb["name"],
                "probable_causes": kb["probable_causes"],
                "immediate_actions": kb["immediate_actions"],
                "maintenance_steps": kb["maintenance_steps"],
                "spares_needed": kb["spares_needed"],
                "estimated_repair_hours": kb["typical_repair_time_hours"],
                "safety_note": kb["safety_note"],
            }
            diagnoses.append(diagnosis)
            all_immediate_actions.extend(kb["immediate_actions"])
            all_spares.extend(kb["spares_needed"])
            total_repair_hours += kb["typical_repair_time_hours"]

    # Deduplicate
    all_immediate_actions = list(dict.fromkeys(all_immediate_actions))
    all_spares = list(dict.fromkeys(all_spares))

    # Determine primary fault
    primary_fault = diagnoses[0] if diagnoses else None

    return {
        "equipment_id": equipment_id,
        "fault_codes_diagnosed": fault_codes,
        "total_faults": len(diagnoses),
        "primary_diagnosis": primary_fault,
        "all_diagnoses": diagnoses,
        "consolidated_immediate_actions": all_immediate_actions[:6],
        "spares_required": all_spares,
        "estimated_total_repair_hours": total_repair_hours,
        "production_impact": _estimate_production_impact(fault_codes, sensor_data),
    }


def _infer_faults_from_sensors(sensor_data: dict) -> list:
    """Infer fault codes from sensor readings when no explicit code provided."""
    faults = []
    vib = float(sensor_data.get("vibration_mm_s", 0))
    temp = float(sensor_data.get("temperature_c", 0))
    pres = float(sensor_data.get("pressure_bar", 5))
    curr = float(sensor_data.get("current_amp", 0))
    oil = float(sensor_data.get("oil_level_pct", 100))

    if vib > 5.0:
        faults.append("E001-BEARING_WEAR")
    elif vib > 3.5:
        faults.append("E006-VIBRATION_HIGH")
    if temp > 100:
        faults.append("E002-OVERHEAT")
    if pres < 2.0:
        faults.append("E003-PRESSURE_LOSS")
    if curr > 200:
        faults.append("E004-OVERCURRENT")
    if oil < 30:
        faults.append("E005-LOW_OIL")

    return faults


def _estimate_production_impact(fault_codes: list, sensor_data: dict) -> dict:
    """Estimate production impact from fault severity."""
    critical_faults = {"E001-BEARING_WEAR", "E002-OVERHEAT", "E004-OVERCURRENT"}
    has_critical = any(f in critical_faults for f in fault_codes)

    if has_critical:
        return {
            "level": "HIGH",
            "description": "Potential production stoppage if unaddressed within 24 hours",
            "estimated_downtime_hours": "4-12",
        }
    elif fault_codes:
        return {
            "level": "MEDIUM",
            "description": "Reduced throughput possible. Schedule maintenance within 72 hours.",
            "estimated_downtime_hours": "1-4",
        }
    else:
        return {
            "level": "LOW",
            "description": "Minor issue. No immediate production impact expected.",
            "estimated_downtime_hours": "0-1",
        }
