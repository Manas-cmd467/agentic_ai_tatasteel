import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'saved')
RUL_MODEL_PATH = os.path.join(MODEL_DIR, 'rul_model.pkl')
RUL_SCALER_PATH = os.path.join(MODEL_DIR, 'rul_scaler.pkl')

# ---------------------------------------------------------------------------
# Feature definition
# ---------------------------------------------------------------------------
SENSOR_FEATURES = [
    'vibration_mm_s',   # mm/s  – vibration severity
    'temperature_c',    # °C    – operating temperature
    'pressure_bar',     # bar   – system pressure
    'current_amp',      # A     – motor current draw
    'rpm',              # rev/min
    'oil_level_pct',    # %     – oil / lubricant level
    'noise_db',         # dB    – acoustic noise
]

# Nominal operating ranges for normalisation
_SENSOR_RANGES = {
    'vibration_mm_s': (0.0, 12.0),
    'temperature_c':  (20.0, 150.0),
    'pressure_bar':   (0.0, 10.0),
    'current_amp':    (0.0, 50.0),
    'rpm':            (0.0, 3600.0),
    'oil_level_pct':  (0.0, 100.0),
    'noise_db':       (40.0, 120.0),
}

# Degradation weights (positive = higher value → more degradation)
_DEGRADATION_WEIGHTS = {
    'vibration_mm_s': 0.30,
    'temperature_c':  0.25,
    'current_amp':    0.20,
    'oil_level_pct':  -0.15,   # inverted: lower oil → higher degradation
    'pressure_bar':   0.10,    # deviation from midpoint used separately
}


class RULPredictor:
    """
    Remaining Useful Life (RUL) predictor for industrial equipment.

    Uses a RandomForestRegressor trained on sensor readings.
    RUL is expressed in hours (range 1 – 720).
    """

    def __init__(self):
        self.model: Optional[RandomForestRegressor] = None
        self.scaler: Optional[StandardScaler] = None
        os.makedirs(MODEL_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalise(self, feature: str, value: float) -> float:
        """Map a raw sensor value to [0, 1] using known operating range."""
        lo, hi = _SENSOR_RANGES.get(feature, (0.0, 1.0))
        if hi == lo:
            return 0.0
        return float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))

    def _compute_degradation_score(self, row: pd.Series) -> float:
        """
        Compute a 0-1 degradation score for a single sensor reading.

        Weights:
            vibration : +0.30
            temperature: +0.25
            current    : +0.20
            oil_level  : -0.15  (inverted – lower oil = worse)
            pressure   : +0.10  (deviation from midpoint)

        Returns:
            Degradation score in [0, 1].  Higher = more degraded.
        """
        score = 0.0
        weight_sum = 0.0

        for feature, weight in _DEGRADATION_WEIGHTS.items():
            raw = float(row.get(feature, 0.0))
            norm = self._normalise(feature, raw)

            if weight < 0:
                # Invert: a lower normalised value means higher degradation
                contribution = abs(weight) * (1.0 - norm)
            else:
                contribution = weight * norm

            score += contribution
            weight_sum += abs(weight)

        # Normalise to ensure output is in [0, 1]
        if weight_sum > 0:
            score = score / weight_sum

        return float(np.clip(score, 0.0, 1.0))

    def _features_from_dict(self, sensor_dict: dict) -> np.ndarray:
        """Convert a sensor reading dict to a 2-D numpy array (1 × n_features)."""
        row = [float(sensor_dict.get(f, 0.0)) for f in SENSOR_FEATURES]
        return np.array(row).reshape(1, -1)

    # ------------------------------------------------------------------
    # Label generation
    # ------------------------------------------------------------------

    def generate_rul_labels(self, df: pd.DataFrame) -> pd.Series:
        """
        Derive synthetic RUL labels from sensor data.

        Formula:
            degradation = _compute_degradation_score(row)
            RUL = 720 * (1 - degradation) + N(0, 20)
            RUL clipped to [1, 720]

        Returns:
            pd.Series of RUL values aligned with *df*.
        """
        degradation_scores = df.apply(self._compute_degradation_score, axis=1)
        noise = np.random.normal(0, 20, size=len(df))
        rul = 720.0 * (1.0 - degradation_scores.values) + noise
        rul = np.clip(rul, 1.0, 720.0)
        return pd.Series(rul, index=df.index, name='rul_hours')

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, df: pd.DataFrame) -> None:
        """
        Train the RUL model on a DataFrame of sensor readings.

        Steps:
            1. Generate RUL labels via generate_rul_labels().
            2. Fit a StandardScaler on SENSOR_FEATURES.
            3. Fit a RandomForestRegressor(n_estimators=150, random_state=42).
            4. Save both model and scaler with joblib.
        """
        print("[RULPredictor] Generating RUL labels...")
        rul_labels = self.generate_rul_labels(df)

        # Keep only columns that exist in the DataFrame
        available_features = [f for f in SENSOR_FEATURES if f in df.columns]
        if not available_features:
            raise ValueError(
                f"[RULPredictor] DataFrame contains none of the expected features: "
                f"{SENSOR_FEATURES}"
            )

        X = df[available_features].fillna(0.0).values
        y = rul_labels.values

        print(f"[RULPredictor] Training on {len(X)} samples with features: {available_features}")

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = RandomForestRegressor(
            n_estimators=150,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_scaled, y)

        print("[RULPredictor] Training complete.  Saving model and scaler...")
        self.save_model()
        print(f"[RULPredictor] Model saved to: {RUL_MODEL_PATH}")

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, sensor_dict: dict) -> dict:
        """
        Predict RUL for a single equipment reading.

        Args:
            sensor_dict: dict mapping SENSOR_FEATURES to their current values.

        Returns:
            dict with keys:
                rul_hours        – float, predicted hours remaining (0-720)
                rul_days         – float, rul_hours / 24
                degradation_pct  – float 0-100, estimated degradation percentage
                confidence       – 'high' | 'medium' | 'low'
                trend            – 'stable' | 'degrading' | 'critical'
        """
        if self.model is None or self.scaler is None:
            raise RuntimeError(
                "[RULPredictor] Model not loaded.  Call load_or_train() first."
            )

        try:
            X = self._features_from_dict(sensor_dict)
            X_scaled = self.scaler.transform(X)
            raw_rul = float(self.model.predict(X_scaled)[0])
            rul_hours = float(np.clip(raw_rul, 0.0, 720.0))

            # Degradation percentage: inverse of how much life remains
            degradation_pct = round((1.0 - rul_hours / 720.0) * 100.0, 1)

            # Confidence
            if rul_hours > 200:
                confidence = 'high'
            elif rul_hours > 72:
                confidence = 'medium'
            else:
                confidence = 'low'

            # Trend
            if degradation_pct < 30:
                trend = 'stable'
            elif degradation_pct < 60:
                trend = 'degrading'
            else:
                trend = 'critical'

            return {
                'rul_hours': round(rul_hours, 2),
                'rul_days': round(rul_hours / 24.0, 2),
                'degradation_pct': degradation_pct,
                'confidence': confidence,
                'trend': trend,
            }

        except Exception as e:
            raise RuntimeError(f"[RULPredictor] Prediction failed: {e}")

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def save_model(self) -> None:
        """Persist model and scaler to disk."""
        try:
            joblib.dump(self.model, RUL_MODEL_PATH)
            joblib.dump(self.scaler, RUL_SCALER_PATH)
        except Exception as e:
            raise RuntimeError(f"[RULPredictor] Failed to save model: {e}")

    def load_model(self) -> bool:
        """
        Load model and scaler from disk.

        Returns:
            True if both files were found and loaded, False otherwise.
        """
        if os.path.isfile(RUL_MODEL_PATH) and os.path.isfile(RUL_SCALER_PATH):
            try:
                self.model = joblib.load(RUL_MODEL_PATH)
                self.scaler = joblib.load(RUL_SCALER_PATH)
                print("[RULPredictor] Model and scaler loaded from disk.")
                return True
            except Exception as e:
                print(f"[RULPredictor] WARNING: Could not load saved model: {e}")
                return False
        return False

    # ------------------------------------------------------------------
    # Smart loader
    # ------------------------------------------------------------------

    def load_or_train(self, data_path: str) -> None:
        """
        Try to load a previously saved model.
        If none exists, train from *data_path* (CSV).
        If the CSV is missing, generate synthetic data and train.

        Args:
            data_path: Path to a CSV file containing sensor readings.
        """
        if self.load_model():
            return

        print("[RULPredictor] No saved model found – training from scratch.")

        if os.path.isfile(data_path):
            print(f"[RULPredictor] Loading training data from: {data_path}")
            try:
                df = pd.read_csv(data_path)
                # Keep only known sensor columns that exist in the CSV
                existing = [f for f in SENSOR_FEATURES if f in df.columns]
                if not existing:
                    raise ValueError("CSV contains no recognised sensor feature columns.")
                self.train(df)
                return
            except Exception as e:
                print(
                    f"[RULPredictor] WARNING: Could not load CSV '{data_path}': {e}. "
                    "Falling back to synthetic data."
                )

        # --- Synthetic data fallback ---
        print("[RULPredictor] Generating synthetic training data (2 000 samples)...")
        np.random.seed(42)
        n = 2000
        synthetic = pd.DataFrame(
            {
                'vibration_mm_s': np.random.uniform(0.5, 10.0, n),
                'temperature_c':  np.random.uniform(30.0, 130.0, n),
                'pressure_bar':   np.random.uniform(1.0, 9.0, n),
                'current_amp':    np.random.uniform(5.0, 45.0, n),
                'rpm':            np.random.uniform(500.0, 3400.0, n),
                'oil_level_pct':  np.random.uniform(10.0, 100.0, n),
                'noise_db':       np.random.uniform(45.0, 110.0, n),
            }
        )
        self.train(synthetic)


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    predictor = RULPredictor()

    data_csv = os.path.join(
        os.path.dirname(__file__), '..', 'data', 'sensor_logs.csv'
    )
    predictor.load_or_train(data_csv)

    sample_reading = {
        'vibration_mm_s': 4.2,
        'temperature_c':  95.0,
        'pressure_bar':   3.5,
        'current_amp':    28.0,
        'rpm':            1800.0,
        'oil_level_pct':  35.0,
        'noise_db':       78.0,
    }

    result = predictor.predict(sample_reading)
    print("\n=== RUL Prediction ===")
    for k, v in result.items():
        print(f"  {k:20s}: {v}")
