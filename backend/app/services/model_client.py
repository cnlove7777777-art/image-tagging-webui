import base64
import json
import logging
import re
from typing import Any, Dict, Optional

from openai import OpenAI, OpenAIError

from app.core.defaults import DEFAULT_CAPTION_PROMPT
from app.core.model_providers import get_provider

logger = logging.getLogger(__name__)


VISION_ANALYSIS_PROMPT = """You are analyzing cosplay / portrait photos for LoRA dataset building.

Return ONLY valid JSON. No markdown, no code fences, no prose outside JSON.

For the main person in the image, output:
1. subject bounding box
2. head bounding box
3. recommended square crop
4. framing and body visibility
5. pose and viewpoint
6. expression
7. occlusion
8. environment and color tags
9. skin exposure / outfit coverage
10. training usefulness

Use normalized coordinates from 0 to 1. When uncertain, use "unclear".
Do not identify the person. Do not infer identity, age, ethnicity, or sensitive attributes.
Focus only on visible body pose, camera framing, clothing visibility, environment, and training usefulness.

Schema:
{
  "subject_bbox": {"x1": 0, "y1": 0, "x2": 1, "y2": 1},
  "head_bbox": {"x1": 0, "y1": 0, "x2": 1, "y2": 1},
  "crop_square": {"cx": 0.5, "cy": 0.5, "side": 1.0},

  "shot_type": "closeup|upper_body|half_body|three_quarter|full_body|long_shot|unclear",
  "body_visibility": "face_only|upper_body|half_body|three_quarter|full_body|unclear",
  "view_angle": "front|side|three_quarter|back|unclear",
  "camera_angle": "eye_level|high_angle|low_angle|unclear",

  "pose_family": "standing|sitting|kneeling|crouching|lying|walking|action|unclear",
  "pose_signature": {
    "torso_direction": "front|side|back|unclear",
    "head_direction": "front|side|up|down|back|unclear",
    "left_arm": "down|raised|bent|near_face|on_waist|holding_prop|occluded|unclear",
    "right_arm": "down|raised|bent|near_face|on_waist|holding_prop|occluded|unclear",
    "left_leg": "straight|bent|crossed|raised|kneeling|occluded|unclear",
    "right_leg": "straight|bent|crossed|raised|kneeling|occluded|unclear",
    "prop_interaction": "none|holding_prop|touching_prop|prop_occludes_body|unclear"
  },

  "expression": "smile|calm|serious|playful|shy|angry|excited|neutral|unclear",
  "expression_intensity": "low|medium|high|unclear",

  "face_occlusion": "none|hair|hand|prop|mask|partial|heavy|unclear",
  "body_occlusion": "none|partial|heavy|unclear",

  "environment": "indoor|outdoor|studio|stage|unknown",
  "background_complexity": "plain|simple|medium|busy|unknown",
  "lighting": "soft|hard|natural|mixed|low_light|unknown",

  "dominant_colors": ["color1", "color2", "color3"],
  "overall_palette": "pastel|vivid|muted|bright|dark|neutral|unknown",
  "color_temperature": "warm|cool|neutral|unknown",

  "skin_exposure_level": "low|medium|high|unclear",
  "outfit_coverage": "full|partial|revealing|unclear",
  "costume_complexity": "simple|medium|detailed|unclear",

  "training_value": "high|medium|low",
  "usable": true,
  "reject_reason": null,
  "confidence": 0.0,
  "reason": "short reason"
}

Crop rule: choose the largest useful square crop that keeps the main subject. Prefer side near 1.0 unless a smaller crop is necessary.
For deduplication, prioritize visible body configuration over emotional expression.
"""


class ModelClient:
    LEGACY_MODEL_PRIORITY = [
        "Qwen/Qwen3-VL-30B-A3B-Instruct",
        "Qwen/Qwen3-VL-32B-Instruct",
        "Qwen/Qwen3-VL-235B-A22B-Instruct",
        "Qwen/Qwen3-VL-8B-Instruct",
    ]

    def __init__(self, api_key: str, base_url: str, model: str, fallback_models: Optional[list[str]] = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.initial_model = model
        self.model = model

        if fallback_models:
            priority = [model] + [m for m in fallback_models if m != model]
        elif model in self.LEGACY_MODEL_PRIORITY:
            priority = self.LEGACY_MODEL_PRIORITY[self.LEGACY_MODEL_PRIORITY.index(model):]
        else:
            # Provider-specific model ids such as DashScope qwen-vl-plus must not fall back
            # to ModelScope-style ids.
            priority = [model]
        self.model_priority = priority
        self.model_index = 0

        logger.info("初始化ModelClient，base_url=%s model=%s", self.base_url, self.model)
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)

    @classmethod
    def from_provider(cls, provider_id: Optional[str] = None, model: Optional[str] = None) -> "ModelClient":
        provider = get_provider(provider_id)
        selected_model = model or provider.default_vision_model or provider.default_focus_model or provider.default_tag_model
        if not selected_model:
            raise RuntimeError(f"Provider {provider.id} has no default model configured")
        if not provider.configured:
            raise RuntimeError(f"Provider {provider.id} is missing API key env {provider.api_key_env}")
        fallback_models = [m.get("id") for m in provider.models if isinstance(m, dict) and m.get("id")]
        return cls(api_key=provider.api_key, base_url=provider.base_url, model=selected_model, fallback_models=fallback_models)

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            base64_data = base64.b64encode(image_file.read()).decode("utf-8")
            return f"data:image/jpeg;base64,{base64_data}"

    def _switch_to_next_model(self) -> bool:
        if self.model_index < len(self.model_priority) - 1:
            self.model_index += 1
            self.model = self.model_priority[self.model_index]
            logger.info("切换到下一个模型: %s", self.model)
            return True
        return False

    def _call_model(self, messages: list, max_tokens: int = 1600) -> str:
        retry_count = 0
        max_retries = max(1, len(self.model_priority))
        while retry_count < max_retries:
            try:
                logger.info("使用模型 %s 调用API...", self.model)
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.2,
                    top_p=0.8,
                )
                return response.choices[0].message.content or ""
            except OpenAIError as exc:
                logger.error("调用模型 %s 时发生错误: %s", self.model, exc)
                if self._switch_to_next_model():
                    retry_count += 1
                    continue
                raise
            except Exception as exc:
                logger.error("调用模型 %s 时发生未知错误: %s", self.model, exc)
                if self._switch_to_next_model():
                    retry_count += 1
                    continue
                raise
        raise RuntimeError("已尝试所有模型，均失败")

    def _messages_for_image(self, image_path: str, prompt: str, system: str) -> list:
        base64_image = self._encode_image(image_path)
        return [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": base64_image}},
                ],
            },
        ]

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        text = (response or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end + 1])
            raise

    def _clamp01(self, value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        return max(0.0, min(1.0, number))

    def _sanitize_bbox(self, bbox: Any) -> Optional[Dict[str, float]]:
        if not isinstance(bbox, dict):
            return None
        x1 = self._clamp01(bbox.get("x1"), 0.0)
        y1 = self._clamp01(bbox.get("y1"), 0.0)
        x2 = self._clamp01(bbox.get("x2"), 1.0)
        y2 = self._clamp01(bbox.get("y2"), 1.0)
        if x2 <= x1 or y2 <= y1:
            return None
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

    def _sanitize_crop_square(self, square: Any) -> Dict[str, float]:
        if not isinstance(square, dict):
            square = {}
        side = self._clamp01(square.get("side"), 1.0)
        side = max(0.05, side)
        return {
            "cx": self._clamp01(square.get("cx"), 0.5),
            "cy": self._clamp01(square.get("cy"), 0.5),
            "side": side,
        }

    def _default_vision_result(self, reason: str = "fallback") -> Dict[str, Any]:
        return {
            "subject_bbox": {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0},
            "head_bbox": None,
            "crop_square": {"cx": 0.5, "cy": 0.5, "side": 1.0},
            "shot_type": "unclear",
            "body_visibility": "unclear",
            "view_angle": "unclear",
            "camera_angle": "unclear",
            "pose_family": "unclear",
            "pose_signature": {
                "torso_direction": "unclear",
                "head_direction": "unclear",
                "left_arm": "unclear",
                "right_arm": "unclear",
                "left_leg": "unclear",
                "right_leg": "unclear",
                "prop_interaction": "unclear",
            },
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
            "usable": False,
            "reject_reason": reason,
            "confidence": 0.0,
            "reason": reason,
        }

    def _sanitize_vision_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = self._default_vision_result("sanitized")
        if isinstance(result, dict):
            cleaned.update(result)
        cleaned["subject_bbox"] = self._sanitize_bbox(cleaned.get("subject_bbox")) or cleaned["subject_bbox"]
        cleaned["head_bbox"] = self._sanitize_bbox(cleaned.get("head_bbox"))
        cleaned["crop_square"] = self._sanitize_crop_square(cleaned.get("crop_square"))
        cleaned["confidence"] = self._clamp01(cleaned.get("confidence"), 0.0)
        cleaned["usable"] = bool(cleaned.get("usable", True))
        if not isinstance(cleaned.get("dominant_colors"), list):
            cleaned["dominant_colors"] = []
        if not isinstance(cleaned.get("pose_signature"), dict):
            cleaned["pose_signature"] = self._default_vision_result()["pose_signature"]
        return cleaned

    def analyze_image(self, image_path: str, retry_hint: Optional[str] = None) -> Dict[str, Any]:
        try:
            prompt = VISION_ANALYSIS_PROMPT
            if retry_hint:
                prompt = f"{prompt}\nNOTE: {retry_hint}"
            messages = self._messages_for_image(
                image_path,
                prompt,
                "You are a precise visual metadata extractor for dataset building. Return only JSON.",
            )
            response = self._call_model(messages, max_tokens=1800)
            return self._sanitize_vision_result(self._parse_json_response(response))
        except Exception as exc:
            logger.error("Failed to analyze image: %s", exc)
            return self._default_vision_result("failed_to_call_model")

    def get_focus_point(self, image_path: str, retry_hint: Optional[str] = None) -> Dict[str, Any]:
        """Backward-compatible focus endpoint backed by structured vision analysis."""
        vision = self.analyze_image(image_path, retry_hint=retry_hint)
        crop_square = vision.get("crop_square") or {"cx": 0.5, "cy": 0.5, "side": 1.0}
        subject_bbox = vision.get("subject_bbox") or {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0}
        return {
            "focus_point": {
                "x": crop_square.get("cx", 0.5),
                "y": crop_square.get("cy", 0.5),
                "side": crop_square.get("side", 1.0),
            },
            "bbox": subject_bbox,
            "shot_type": vision.get("shot_type", "unclear"),
            "confidence": vision.get("confidence", 0.0),
            "usable": vision.get("usable", True),
            "reject_reason": vision.get("reject_reason"),
            "reason": vision.get("reason", ""),
            "vision": vision,
        }

    def generate_tags(self, image_path: str) -> Dict[str, Any]:
        try:
            prompt = """Return ONLY one-line JSON (no markdown/backticks).
Task: generate training caption + tags for ONE portrait photo.

Output schema:
{
  "caption": "one short English caption, <= 25 words",
  "tags": ["comma-free tag", "comma-free tag"],
  "has_face": true,
  "shot_type": "closeup|medium|long",
  "notes": "short"
}
Rules:
- Describe clothing, hair color, pose, background, lighting.
- Avoid sensitive identity guesses.
"""
            messages = self._messages_for_image(
                image_path,
                prompt,
                "You are a professional image tagger. Generate concise, relevant tags and caption.",
            )
            return self._parse_json_response(self._call_model(messages))
        except Exception as exc:
            logger.error("Failed to generate tags: %s", exc)
            return {
                "caption": "unknown person, portrait",
                "tags": ["person", "portrait", "unknown"],
                "has_face": True,
                "shot_type": "medium",
                "notes": "failed to call model, using default tags",
            }

    def generate_caption(self, image_path: str, prompt: Optional[str] = None) -> str:
        try:
            caption_prompt = prompt or DEFAULT_CAPTION_PROMPT
            messages = self._messages_for_image(
                image_path,
                caption_prompt,
                "You are a precise dataset captioner for portrait/cosplay photos. Avoid speculation and keep concise.",
            )
            return self._call_model(messages).strip()
        except Exception as exc:
            logger.error("Failed to generate caption: %s", exc)
            return "portrait photo, clean background, soft light\ntags: portrait,photo,soft light"
