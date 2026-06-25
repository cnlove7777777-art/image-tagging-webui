from __future__ import annotations

from typing import Any, Dict, Optional


DEFAULT_POSE_SIGNATURE = {
    "torso_direction": "unclear",
    "head_direction": "unclear",
    "left_arm": "unclear",
    "right_arm": "unclear",
    "left_leg": "unclear",
    "right_leg": "unclear",
    "prop_interaction": "unclear",
}


DEFAULT_VISION = {
    "subject_bbox": {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0},
    "head_bbox": None,
    "crop_square": {"cx": 0.5, "cy": 0.5, "side": 1.0},
    "shot_type": "unclear",
    "body_visibility": "unclear",
    "view_angle": "unclear",
    "camera_angle": "unclear",
    "pose_family": "unclear",
    "pose_signature": DEFAULT_POSE_SIGNATURE,
    "expression": "unclear",
    "expression_intensity": "unclear",
    "face_occlusion": "unclear",
    "body_occlusion": "unclear",
    "environment": "unknown",
    "background_complexity": "unknown",
    "lighting": "unknown",
    "dominant_colors": [],
    "overall_palette": "unknown",
    "color_temperature": "unknown",
    "skin_exposure_level": "unclear",
    "outfit_coverage": "unclear",
    "costume_complexity": "unclear",
    "training_value": "medium",
    "usable": True,
    "reject_reason": None,
    "confidence": 0.0,
    "reason": "",
}


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def normalize_bbox(value: Any) -> Optional[Dict[str, float]]:
    if not isinstance(value, dict):
        return None
    x1 = clamp01(value.get("x1"), 0.0)
    y1 = clamp01(value.get("y1"), 0.0)
    x2 = clamp01(value.get("x2"), 1.0)
    y2 = clamp01(value.get("y2"), 1.0)
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def normalize_crop_square(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        value = {}
    side = max(0.05, clamp01(value.get("side"), 1.0))
    return {
        "cx": clamp01(value.get("cx"), 0.5),
        "cy": clamp01(value.get("cy"), 0.5),
        "side": side,
    }


def normalize_vision(value: Any) -> Dict[str, Any]:
    result = dict(DEFAULT_VISION)
    result["pose_signature"] = dict(DEFAULT_POSE_SIGNATURE)

    if isinstance(value, dict):
        result.update(value)
        if isinstance(value.get("pose_signature"), dict):
            result["pose_signature"] = {**DEFAULT_POSE_SIGNATURE, **value["pose_signature"]}

    result["subject_bbox"] = normalize_bbox(result.get("subject_bbox")) or DEFAULT_VISION["subject_bbox"]
    result["head_bbox"] = normalize_bbox(result.get("head_bbox"))
    result["crop_square"] = normalize_crop_square(result.get("crop_square"))
    result["confidence"] = clamp01(result.get("confidence"), 0.0)
    result["usable"] = bool(result.get("usable", True))
    if not isinstance(result.get("dominant_colors"), list):
        result["dominant_colors"] = []
    return result


def focus_result_from_vision(vision: Dict[str, Any]) -> Dict[str, Any]:
    vision = normalize_vision(vision)
    square = vision["crop_square"]
    return {
        "focus_point": {"x": square["cx"], "y": square["cy"], "side": square["side"]},
        "bbox": vision["subject_bbox"],
        "shot_type": vision.get("shot_type", "unclear"),
        "confidence": vision.get("confidence", 0.0),
        "usable": vision.get("usable", True),
        "reject_reason": vision.get("reject_reason"),
        "reason": vision.get("reason", ""),
        "vision": vision,
    }


def subject_area_ratio(vision: Dict[str, Any]) -> float:
    bbox = normalize_vision(vision)["subject_bbox"]
    return max(0.0, min(1.0, (bbox["x2"] - bbox["x1"]) * (bbox["y2"] - bbox["y1"])))
