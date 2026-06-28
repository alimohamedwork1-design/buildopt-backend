from typing import Any, Dict, List

import numpy as np


class AnomalyDetector:
    def __init__(self, demo_mode: bool = True) -> None:
        self.demo_mode = demo_mode
        self._model = None
        if not demo_mode:
            try:
                from sklearn.ensemble import IsolationForest

                self._model = IsolationForest(contamination=0.05, random_state=42)
            except Exception:
                self._model = None

    def detect(self, metrics: List[Dict[str, float]]) -> List[Dict[str, Any]]:
        if not metrics:
            return []

        if self.demo_mode or self._model is None:
            return [
                {
                    "index": idx,
                    "is_anomaly": metric.get("total_kw", 0) > 900,
                    "score": -0.12 if metric.get("total_kw", 0) > 900 else 0.45,
                }
                for idx, metric in enumerate(metrics)
            ]

        matrix = np.array([[m.get("total_kw", 0), m.get("hvac_kw", 0), m.get("temp_c", 0)] for m in metrics])
        predictions = self._model.fit_predict(matrix)
        scores = self._model.decision_function(matrix)
        return [
            {"index": idx, "is_anomaly": pred == -1, "score": float(score)}
            for idx, (pred, score) in enumerate(zip(predictions, scores))
        ]
