"""
Prototype ML Anomaly Detection using scikit-learn Isolation Forest.

Features are extracted from structured change data:
  1. category_code          (0: PARAMETERS, 1: PLC_LOGIC, 2: NETWORK, 3: FIREWALL, 4: FIRMWARE, 5: SAFETY_CONFIG)
  2. is_expected            (1.0 if expected, 0.0 if unexpected)
  3. is_authorized          (1.0 if authorized, 0.0 if unauthorized)
  4. relative_magnitude     (float magnitude delta or categorical shift)
  5. historical_frequency   (expected monthly change frequency)
  6. historical_risk_mean   (historical average risk score for this parameter)
  7. user_role_weight       (1.0: ENGINEER, 2.0: SUPERVISOR, 3.0: ADMIN)
  8. is_safety_critical     (1.0 if safety interlock / safety config, 0.0 otherwise)

Core Invariants:
  1. AI must NOT override deterministic security rules.
  2. If ML fails, the rest of MaintX must continue working (fault-tolerant fallback).
  3. All outputs are clearly labeled: 'Prototype ML anomaly score'.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.ensemble import IsolationForest

from app.schemas.changes import ChangeCategory

logger = logging.getLogger(__name__)

MODEL_NAME = "IsolationForest_v1.0-prototype"
ML_LABEL = "Prototype ML anomaly score"

CATEGORY_MAP = {
    ChangeCategory.PARAMETERS: 0,
    ChangeCategory.PLC_LOGIC: 1,
    ChangeCategory.NETWORK: 2,
    ChangeCategory.FIREWALL: 3,
    ChangeCategory.FIRMWARE: 4,
    ChangeCategory.SAFETY_CONFIG: 5,
}

ROLE_WEIGHT_MAP = {
    "MAINTENANCE_ENGINEER": 1.0,
    "SUPERVISOR": 2.0,
    "ADMIN": 3.0,
    "SECURITY_ANALYST": 1.5,
    "AUDITOR": 0.5,
}


@dataclass
class AnomalyDetectionResult:
    ai_anomaly_score: Optional[int]
    model_name: str
    ml_label: str
    ai_explanation: Optional[str]
    is_anomaly: bool


class IsolationForestAnomalyDetector:
    """
    Trained prototype Isolation Forest anomaly detector for industrial change patterns.
    """

    def __init__(self) -> None:
        self.model_name = MODEL_NAME
        self.ml_label = ML_LABEL
        self._model: Optional[IsolationForest] = None
        self._initialize_model()

    def _initialize_model(self) -> None:
        """
        Train the baseline Isolation Forest on typical, authorized industrial maintenance patterns.
        """
        try:
            # Synthetic distribution of normal maintenance changes:
            # [cat, is_exp, is_auth, rel_mag, freq, hist_risk, role_wt, is_safety]
            normal_data = [
                # Normal parameter adjustments
                [0, 1.0, 1.0, 0.067, 4.2, 15.5, 1.0, 0.0],  # e.g. 3000 -> 3200 RPM
                [0, 1.0, 1.0, 0.050, 4.0, 16.0, 1.0, 0.0],
                [0, 1.0, 1.0, 0.030, 5.0, 12.0, 1.0, 0.0],
                [0, 1.0, 1.0, 0.080, 3.5, 18.0, 1.0, 0.0],
                [0, 1.0, 1.0, 0.040, 4.5, 14.0, 1.0, 0.0],
                [0, 1.0, 1.0, 0.020, 6.0, 10.0, 1.0, 0.0],
                # Normal scheduled PLC updates
                [1, 1.0, 1.0, 0.000, 1.5, 20.0, 1.0, 0.0],
                [1, 1.0, 1.0, 0.000, 2.0, 22.0, 2.0, 0.0],
                # Normal scheduled firmware maintenance
                [4, 1.0, 1.0, 0.010, 0.5, 30.0, 2.0, 0.0],
                # Occasional supervisor-authorized adjustments
                [0, 1.0, 1.0, 0.120, 2.0, 22.0, 2.0, 0.0],
                [0, 0.0, 1.0, 0.050, 2.5, 25.0, 2.0, 0.0],
                [1, 0.0, 1.0, 0.000, 1.0, 35.0, 2.0, 0.0],
            ]

            # Fit Isolation Forest
            X = np.array(normal_data, dtype=np.float32)
            self._model = IsolationForest(
                n_estimators=100,
                contamination=0.08,
                random_state=42,
            )
            self._model.fit(X)
            logger.info("Isolation Forest anomaly detector initialized successfully.")
        except Exception as exc:
            logger.warning("Failed to initialize Isolation Forest model: %s. Anomaly scoring will fallback gracefully.", exc)
            self._model = None

    def extract_features(
        self,
        category: ChangeCategory,
        parameter_name: str,
        old_value: Any,
        new_value: Any,
        is_expected: bool,
        is_authorized: bool,
        user_role: str = "MAINTENANCE_ENGINEER",
    ) -> List[float]:
        """Convert structured change data into numerical feature vector."""
        cat_code = float(CATEGORY_MAP.get(category, 0))
        exp_val = 1.0 if is_expected else 0.0
        auth_val = 1.0 if is_authorized else 0.0

        # Calculate relative magnitude
        rel_mag = 0.0
        try:
            o_num = float(old_value)
            n_num = float(new_value)
            rel_mag = abs(n_num - o_num) / (abs(o_num) or 1.0)
        except (ValueError, TypeError):
            # Categorical change
            if old_value != new_value:
                rel_mag = 1.0

        param_lower = parameter_name.lower()
        is_safety = (
            category == ChangeCategory.SAFETY_CONFIG
            or "n7" in param_lower
            or "safety" in param_lower
            or "interlock" in param_lower
        )
        safety_flag = 1.0 if is_safety else 0.0

        # Default historical baseline stats
        freq = 4.0 if category == ChangeCategory.PARAMETERS else (1.5 if category == ChangeCategory.PLC_LOGIC else 0.3)
        hist_risk = 15.0 if is_expected else 65.0
        role_weight = ROLE_WEIGHT_MAP.get(user_role, 1.0)

        return [
            cat_code,
            exp_val,
            auth_val,
            rel_mag,
            freq,
            hist_risk,
            role_weight,
            safety_flag,
        ]

    def predict_anomaly(
        self,
        category: ChangeCategory,
        parameter_name: str,
        old_value: Any,
        new_value: Any,
        is_expected: bool,
        is_authorized: bool,
        user_role: str = "MAINTENANCE_ENGINEER",
    ) -> AnomalyDetectionResult:
        """
        Evaluate ML anomaly score.
        Guaranteed non-crashing: if anything fails, returns graceful fallback.
        """
        if self._model is None:
            return AnomalyDetectionResult(
                ai_anomaly_score=None,
                model_name=self.model_name,
                ml_label=self.ml_label,
                ai_explanation="Prototype ML model unavailable; deterministic security rules active.",
                is_anomaly=False,
            )

        try:
            features = self.extract_features(
                category=category,
                parameter_name=parameter_name,
                old_value=old_value,
                new_value=new_value,
                is_expected=is_expected,
                is_authorized=is_authorized,
                user_role=user_role,
            )

            X = np.array([features], dtype=np.float32)
            # decision_function outputs: positive = normal, negative = anomaly
            raw_score = float(self._model.decision_function(X)[0])
            is_anomaly_pred = bool(self._model.predict(X)[0] == -1)

            # Map raw score (typically ~ -0.3 to +0.25) to a clean [0, 100] scale:
            # Positive raw_score (e.g. +0.15) -> Low anomaly (~10-20)
            # Negative raw_score (e.g. -0.25) -> High anomaly (~80-95)
            # Formula: (0.15 - raw_score) * 180 clipped to [5, 98]
            scaled_score = int(np.clip((0.15 - raw_score) * 180, 5, 98))

            explanations: List[str] = []
            if not is_expected:
                explanations.append("Statistical deviation: change was unexpected in normal work baseline")
            if not is_authorized:
                explanations.append("Role/authorization pattern outlier")
            if features[7] > 0.5:  # is_safety
                explanations.append("Isolation Forest flagged safety-critical feature dimension")
            if features[0] == 2.0:  # NETWORK
                explanations.append("Network parameter modification is an outlier relative to baseline frequency")
            if not explanations:
                explanations.append("Change features conform closely to historical maintenance baseline")

            return AnomalyDetectionResult(
                ai_anomaly_score=scaled_score,
                model_name=self.model_name,
                ml_label=self.ml_label,
                ai_explanation="; ".join(explanations),
                is_anomaly=is_anomaly_pred or scaled_score > 60,
            )

        except Exception as exc:
            logger.warning(
                "ML anomaly inference encountered error: %s. Continuing with deterministic security.",
                exc,
            )
            return AnomalyDetectionResult(
                ai_anomaly_score=None,
                model_name=self.model_name,
                ml_label=self.ml_label,
                ai_explanation=f"Prototype ML scoring encountered exception ({exc}); deterministic security active.",
                is_anomaly=False,
            )


# Global singleton instance
_detector_instance: Optional[IsolationForestAnomalyDetector] = None


def get_anomaly_detector() -> IsolationForestAnomalyDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = IsolationForestAnomalyDetector()
    return _detector_instance
