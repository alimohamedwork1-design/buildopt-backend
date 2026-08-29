"""Semantic mapping pipeline with confidence scores."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.metasys_auto_mapper import _NAME_RULES

AUTO_MAP_THRESHOLD = 0.95
REVIEW_THRESHOLD = 0.75


def _confidence_from_score(score: int) -> float:
    if score <= 0:
        return 0.0
    return min(0.99, round(0.55 + score / 200, 2))


def classify_point(label: str, patterns: List[str]) -> tuple[int, float]:
    text = label.lower()
    for i, pat in enumerate(patterns):
        if re.search(pat, text, re.IGNORECASE):
            score = 100 - i
            return score, _confidence_from_score(score)
    return 0, 0.0


def suggest_semantic_mappings(
    objects: List[Dict[str, str]],
    existing: Optional[Dict[str, str]] = None,
    *,
    merge: bool = True,
) -> List[Dict[str, Any]]:
    existing = dict(existing or {})
    used_ids = set(existing.values())
    candidates: List[Dict[str, Any]] = []

    for key, patterns in _NAME_RULES:
        if merge and key in existing and existing[key]:
            candidates.append(
                {
                    "logical_key": key,
                    "canonical_name": key,
                    "object_id": existing[key],
                    "confidence": 1.0,
                    "status": "APPROVED",
                    "reason": "existing mapping",
                }
            )
            continue

        best_id = ""
        best_score = 0
        best_label = ""
        for obj in objects:
            oid = obj["id"]
            if oid in used_ids:
                continue
            label = obj.get("label") or obj.get("name") or ""
            score, _ = classify_point(label, patterns)
            if score > best_score:
                best_score = score
                best_id = oid
                best_label = label

        if not best_id or best_score <= 0:
            candidates.append(
                {
                    "logical_key": key,
                    "canonical_name": key,
                    "object_id": None,
                    "confidence": 0.0,
                    "status": "UNMAPPED",
                    "reason": "no match",
                }
            )
            continue

        conf = _confidence_from_score(best_score)
        if conf >= AUTO_MAP_THRESHOLD:
            status = "AUTO_CANDIDATE"
        elif conf >= REVIEW_THRESHOLD:
            status = "REVIEW_REQUIRED"
        else:
            status = "UNMAPPED"

        candidates.append(
            {
                "logical_key": key,
                "canonical_name": key,
                "object_id": best_id,
                "vendor_name": best_label,
                "confidence": conf,
                "status": status,
                "reason": f"pattern match score {best_score}",
            }
        )
        if status == "AUTO_CANDIDATE":
            used_ids.add(best_id)

    return candidates
