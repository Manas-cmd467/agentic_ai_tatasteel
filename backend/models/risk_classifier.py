"""
risk_classifier.py
------------------
Rule-based risk scoring and equipment prioritisation for the
Maintenance Wizard project.
"""

from __future__ import annotations

from typing import Any


class RiskClassifier:
    """
    Rule-based risk classifier for industrial equipment.

    Usage
    -----
    classifier = RiskClassifier()
    result = classifier.classify_risk(sensor_dict, fault_codes, rul_hours)
    """

    # ------------------------------------------------------------------
    # Scoring rule tables
    # ------------------------------------------------------------------

    # (condition_callable, score_delta, human_readable_label)
    _CRITICAL_RULES = [
        (lambda s, c, r: s.get('temperature_c', 0) > 120,       40, "Temperature CRITICAL (>120°C)"),
        (lambda s, c, r: s.get('vibration_mm_s', 0) > 8,        40, "Vibration CRITICAL (>8 mm/s)"),
        (lambda s, c, r: r < 24,                                  40, "RUL CRITICAL (<24 hours)"),
        (lambda s, c, r: s.get('pressure_bar', 9999) < 0.5,      40, "Pressure CRITICAL (<0.5 bar)"),
        (lambda s, c, r: 'E002-OVERHEAT' in c,                   40, "Fault code: E002-OVERHEAT"),
        (lambda s, c, r: 'E004-OVERCURRENT' in c,                40, "Fault code: E004-OVERCURRENT"),
    ]

    _HIGH_RULES = [
        (lambda s, c, r: s.get('temperature_c', 0) > 100,        25, "Temperature HIGH (>100°C)"),
        (lambda s, c, r: s.get('vibration_mm_s', 0) > 5,         25, "Vibration HIGH (>5 mm/s)"),
        (lambda s, c, r: r < 72,                                  25, "RUL HIGH (<72 hours)"),
        (lambda s, c, r: s.get('oil_level_pct', 100) < 20,       25, "Oil level critically LOW (<20%)"),
    ]

    _MEDIUM_RULES = [
        (lambda s, c, r: s.get('temperature_c', 0) > 85,         15, "Temperature elevated (>85°C)"),
        (lambda s, c, r: s.get('vibration_mm_s', 0) > 3,         15, "Vibration elevated (>3 mm/s)"),
        (lambda s, c, r: r < 168,                                 15, "RUL MEDIUM (<168 hours / 7 days)"),
        (lambda s, c, r: s.get('oil_level_pct', 100) < 40,       15, "Oil level LOW (<40%)"),
    ]

    _LOW_RULES = [
        (lambda s, c, r: s.get('temperature_c', 0) > 75,          5, "Temperature slightly elevated (>75°C)"),
        (lambda s, c, r: s.get('vibration_mm_s', 0) > 2,          5, "Vibration slightly elevated (>2 mm/s)"),
        (lambda s, c, r: r < 336,                                   5, "RUL LOW (<336 hours / 14 days)"),
    ]

    # ------------------------------------------------------------------
    # Urgency and action mappings
    # ------------------------------------------------------------------

    _URGENCY_MAP = {
        'CRITICAL': 'IMMEDIATE – Stop equipment now and escalate to maintenance team.',
        'HIGH':     'URGENT – Schedule maintenance within 24 hours.',
        'MEDIUM':   'PLANNED – Schedule maintenance within the next 7 days.',
        'LOW':      'MONITOR – Continue monitoring; maintenance at next scheduled interval.',
    }

    _ACTION_MAP = {
        'CRITICAL': (
            "IMMEDIATE SHUTDOWN REQUIRED. Dispatch maintenance crew immediately. "
            "Conduct full inspection of bearings, seals, electrical connections, "
            "and lubrication system. Do not restart until root cause is identified "
            "and resolved. Log incident in maintenance management system."
        ),
        'HIGH': (
            "Schedule urgent maintenance within 24 hours. Pre-order replacement "
            "parts if bearings or seals are suspected. Increase sensor polling "
            "frequency to every 15 minutes. Notify shift supervisor and maintenance "
            "lead. Prepare contingency plan for temporary equipment shutdown."
        ),
        'MEDIUM': (
            "Schedule preventive maintenance within 7 days. Review last maintenance "
            "record, check lubrication levels, inspect for early signs of wear. "
            "Update maintenance log with current readings. Monitor trends daily."
        ),
        'LOW': (
            "Continue normal operation. Log current sensor readings. "
            "Ensure next scheduled maintenance is not overdue. "
            "Monitor for any upward trends in vibration or temperature."
        ),
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_risk(
        self,
        sensor_dict: dict,
        fault_codes: list,
        rul_hours: float,
    ) -> dict:
        """
        Compute a risk score and derive a risk level from sensor readings,
        active fault codes, and predicted RUL.

        Args:
            sensor_dict : dict of sensor readings (keys match SENSOR_FEATURES).
            fault_codes : list of active fault code strings (e.g. ['E002-OVERHEAT']).
            rul_hours   : Predicted remaining useful life in hours.

        Returns:
            dict with keys:
                risk_score           – int 0-100
                risk_level           – 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
                intervention_urgency – human-readable urgency string
                recommended_action   – detailed action string
                factors              – list[str] of triggered condition descriptions
        """
        try:
            fault_codes = [str(c).strip().upper() for c in (fault_codes or [])]
            rul_hours = float(rul_hours) if rul_hours is not None else 720.0

            base_score = 0
            factors: list[str] = []

            rule_groups = [
                self._CRITICAL_RULES,
                self._HIGH_RULES,
                self._MEDIUM_RULES,
                self._LOW_RULES,
            ]

            for rule_group in rule_groups:
                for condition_fn, delta, label in rule_group:
                    try:
                        if condition_fn(sensor_dict, fault_codes, rul_hours):
                            base_score += delta
                            factors.append(label)
                    except Exception:
                        # Skip any single rule evaluation error gracefully
                        continue

            # Cap at 100
            risk_score = min(base_score, 100)

            # Determine risk level
            if risk_score >= 80:
                risk_level = 'CRITICAL'
            elif risk_score >= 50:
                risk_level = 'HIGH'
            elif risk_score >= 25:
                risk_level = 'MEDIUM'
            else:
                risk_level = 'LOW'

            return {
                'risk_score': risk_score,
                'risk_level': risk_level,
                'intervention_urgency': self._URGENCY_MAP[risk_level],
                'recommended_action': self._ACTION_MAP[risk_level],
                'factors': factors,
            }

        except Exception as e:
            # Return a safe default if something goes wrong
            return {
                'risk_score': 0,
                'risk_level': 'LOW',
                'intervention_urgency': self._URGENCY_MAP['LOW'],
                'recommended_action': self._ACTION_MAP['LOW'],
                'factors': [],
                'error': str(e),
            }

    def prioritize_equipment(self, equipment_list: list) -> list:
        """
        Sort a list of equipment result dicts by risk_score (descending).

        Each item in *equipment_list* is expected to already contain a
        'risk_score' key (as returned by classify_risk).  Items without
        the key are treated as score = 0.

        Args:
            equipment_list: List of equipment dicts with risk information.

        Returns:
            New list sorted by risk_score descending (highest risk first).
        """
        try:
            return sorted(
                equipment_list,
                key=lambda item: item.get('risk_score', 0),
                reverse=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"[RiskClassifier] Failed to prioritise equipment list: {e}"
            )


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    classifier = RiskClassifier()

    # Test 1 – critical scenario
    sensors_critical = {
        'vibration_mm_s': 9.5,
        'temperature_c':  125.0,
        'pressure_bar':   0.3,
        'current_amp':    48.0,
        'rpm':            3200.0,
        'oil_level_pct':  10.0,
        'noise_db':       105.0,
    }
    result = classifier.classify_risk(sensors_critical, ['E002-OVERHEAT', 'E004-OVERCURRENT'], 18)
    print("=== Critical Scenario ===")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Test 2 – low risk scenario
    sensors_ok = {
        'vibration_mm_s': 1.2,
        'temperature_c':  65.0,
        'pressure_bar':   5.0,
        'current_amp':    20.0,
        'rpm':            1500.0,
        'oil_level_pct':  80.0,
        'noise_db':       60.0,
    }
    result_ok = classifier.classify_risk(sensors_ok, [], 600)
    print("\n=== Low Risk Scenario ===")
    for k, v in result_ok.items():
        print(f"  {k}: {v}")

    # Test 3 – prioritisation
    equipment = [
        {'equipment_id': 'EQ-01', 'risk_score': 35},
        {'equipment_id': 'EQ-02', 'risk_score': 85},
        {'equipment_id': 'EQ-03', 'risk_score': 10},
        {'equipment_id': 'EQ-04', 'risk_score': 60},
    ]
    prioritised = classifier.prioritize_equipment(equipment)
    print("\n=== Equipment Priority Order ===")
    for eq in prioritised:
        print(f"  {eq['equipment_id']} -> score {eq['risk_score']}")
