from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.services.vision_metadata import normalize_vision


POSE_KEYS = [
    "torso_direction",
    "head_direction",
    "left_arm",
    "right_arm",
    "left_leg",
    "right_leg",
    "prop_interaction",
]


def _eq_score(a: Any, b: Any, weight: float, unclear: str = "unclear") -> Tuple[float, str | None]:
    if not a or not b or a == unclear or b == unclear:
        return 0.0, None
    if a == b:
        return weight, str(a)
    return 0.0, None


def _bbox_close_score(a: Dict[str, float], b: Dict[str, float]) -> float:
    acx = (a["x1"] + a["x2"]) / 2
    acy = (a["y1"] + a["y2"]) / 2
    aw = a["x2"] - a["x1"]
    ah = a["y2"] - a["y1"]
    bcx = (b["x1"] + b["x2"]) / 2
    bcy = (b["y1"] + b["y2"]) / 2
    bw = b["x2"] - b["x1"]
    bh = b["y2"] - b["y1"]
    center_delta = abs(acx - bcx) + abs(acy - bcy)
    size_delta = abs(aw - bw) + abs(ah - bh)
    # Small motion/scale changes are okay; large crop/layout changes should not be merged.
    score = max(0.0, 1.0 - center_delta * 3.0 - size_delta * 2.0)
    return min(1.0, score)


def semantic_similarity(a_raw: Dict[str, Any], b_raw: Dict[str, Any]) -> Dict[str, Any]:
    """Score whether two analyzed images are semantically redundant.

    The score is intentionally conservative: it is for cosplay/portrait dataset
    curation where deleting too much is worse than keeping a few similar images.
    """
    a = normalize_vision(a_raw)
    b = normalize_vision(b_raw)
    score = 0.0
    max_score = 0.0
    reasons: List[str] = []

    for key, weight in [
        ("shot_type", 1.0),
        ("body_visibility", 1.0),
        ("pose_family", 2.0),
        ("view_angle", 1.5),
        ("camera_angle", 0.5),
        ("face_occlusion", 0.5),
        ("body_occlusion", 0.5),
    ]:
        max_score += weight
        add, reason = _eq_score(a.get(key), b.get(key), weight, unclear="unclear")
        score += add
        if reason:
            reasons.append(f"{key}:{reason}")

    a_pose = a.get("pose_signature") or {}
    b_pose = b.get("pose_signature") or {}
    for key in POSE_KEYS:
        weight = 1.0
        max_score += weight
        add, reason = _eq_score(a_pose.get(key), b_pose.get(key), weight, unclear="unclear")
        score += add
        if reason:
            reasons.append(f"pose.{key}:{reason}")

    bbox_weight = 2.0
    max_score += bbox_weight
    bbox_score = _bbox_close_score(a["subject_bbox"], b["subject_bbox"])
    score += bbox_score * bbox_weight
    if bbox_score >= 0.75:
        reasons.append("subject_bbox:close")

    normalized = score / max(1.0, max_score)
    return {
        "score": round(normalized, 4),
        "is_similar": normalized >= 0.72,
        "reasons": reasons,
    }


def should_keep_over(candidate: Dict[str, Any], current: Dict[str, Any]) -> bool:
    """Return True if candidate should replace current as cluster representative."""
    value_rank = {"high": 3, "medium": 2, "low": 1}
    cand = normalize_vision(candidate)
    cur = normalize_vision(current)
    cand_value = value_rank.get(str(cand.get("training_value", "medium")), 2)
    cur_value = value_rank.get(str(cur.get("training_value", "medium")), 2)
    if cand_value != cur_value:
        return cand_value > cur_value
    return float(cand.get("confidence", 0.0)) > float(cur.get("confidence", 0.0))
