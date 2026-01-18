import os
import base64
import json
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI


class ModelClient:
    def __init__(self, model: str):
        api_key = os.environ.get("MODELSCOPE_TOKEN")
        base_url = os.environ.get("BASE_URL", "https://api-inference.modelscope.cn/v1/")
        
        if not api_key:
            raise ValueError("MODELSCOPE_TOKEN 环境变量未设置")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def _call_model(self, messages: list) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1024,
            temperature=0.1,
        )
        return response.choices[0].message.content

    def get_focus_point(self, image_path: str, retry_hint: Optional[str] = None) -> Dict[str, Any]:
        base64_image = self._encode_image(image_path)

        prompt = """Analyze this image and identify the main focus point. Return a JSON object with:
        - focus_point: {x, y, side} normalized (0-1). side is the square crop ratio based on the short edge.
        - bbox: optional {x1, y1, x2, y2} normalized bounding box
        - shot_type: optional "closeup", "medium", or "long"
        - confidence: 0.0-1.0 confidence score
        - reason: short reason for the focus point
        - model_used: the model name used for this prediction

        Crop rule: choose the LARGEST possible square crop. Prefer side=1.0 (use the full short edge).
        Only reduce side if needed to fully include the main subject.
        Only return valid JSON, no additional text."""
        if retry_hint:
            prompt = f"{prompt}\nNOTE: {retry_hint}"

        messages = [
            {
                "role": "system",
                "content": "You are a professional image analyst. Focus on identifying the main subject and its exact position."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]

        try:
            response = self._call_model(messages)
            result = json.loads(response)
            
            # Validate the result
            if "focus_point" not in result:
                result["focus_point"] = {"x": 0.5, "y": 0.5}
                result["confidence"] = 0.0
            
            # Normalize coordinates if needed
            for key in ["focus_point", "bbox"]:
                if key in result and result[key]:
                    for coord in result[key]:
                        result[key][coord] = max(0.0, min(1.0, result[key][coord]))
            
            # Add model used
            result["model_used"] = self.model
            
            return result
        except json.JSONDecodeError:
            return {
                "focus_point": {"x": 0.5, "y": 0.5},
                "bbox": None,
                "shot_type": None,
                "confidence": 0.0,
                "reason": "failed to parse response",
                "model_used": self.model,
            }

    def generate_tags(self, image_path: str) -> str:
        base64_image = self._encode_image(image_path)

        prompt = """Generate concise English tags for this image, separated by commas. Include:
        - main subject
        - hair color
        - clothing
        - shot distance
        - composition
        - lighting
        - background

        Example: woman, black hair, dress, closeup, portrait, soft lighting, indoor

        Only return tags, no additional text."""

        messages = [
            {
                "role": "system",
                "content": "You are a professional image tagger. Generate concise, relevant tags."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]

        response = self._call_model(messages)
        # Clean up response
        response = response.strip()
        response = response.replace("\n", "")
        return response
