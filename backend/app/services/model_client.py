import base64
import time
import json
import logging
from typing import Dict, Optional, Any
from openai import OpenAI
from openai import OpenAIError
from app.core.defaults import DEFAULT_CAPTION_PROMPT

logger = logging.getLogger(__name__)


class ModelClient:
    # 模型优先级列表 - 仅包含VL模型
    MODEL_PRIORITY = [
        "Qwen/Qwen3-VL-30B-A3B-Instruct",  # 优先使用30B A3B模型
        "Qwen/Qwen3-VL-32B-Instruct",       # 然后使用32B模型
        "Qwen/Qwen3-VL-235B-A22B-Instruct",  # 然后使用235B A22B模型
        "Qwen/Qwen3-VL-8B-Instruct"         # 最后使用8B模型
    ]
    
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.initial_model = model
        self.model = model
        self.model_index = 0
        
        # 初始化模型索引
        if model in self.MODEL_PRIORITY:
            self.model_index = self.MODEL_PRIORITY.index(model)
        
        logger.info(f"初始化ModelClient，使用模型: {self.model}")
        
        # Create OpenAI client
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0
        )

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            base64_data = base64.b64encode(image_file.read()).decode("utf-8")
            # 返回完整的Base64 Data URL格式
            return f"data:image/jpeg;base64,{base64_data}"

    def _switch_to_next_model(self) -> bool:
        """切换到下一个优先级的模型"""
        if self.model_index < len(self.MODEL_PRIORITY) - 1:
            self.model_index += 1
            self.model = self.MODEL_PRIORITY[self.model_index]
            logger.info(f"切换到下一个模型: {self.model}")
            return True
        return False

    def _call_model(self, messages: list) -> str:
        retry_count = 0
        max_retries = len(self.MODEL_PRIORITY)
        
        while retry_count < max_retries:
            try:
                logger.info(f"使用模型 {self.model} 调用API...")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=1024,
                    temperature=0.2,
                    top_p=0.8
                )
                return response.choices[0].message.content
                
            except OpenAIError as e:
                logger.error(f"调用模型 {self.model} 时发生错误: {str(e)}")
                
                # 切换到下一个模型
                logger.warning(f"模型 {self.model} 调用失败，尝试切换模型...")
                if self._switch_to_next_model():
                    retry_count += 1
                    continue
                else:
                    logger.error("已尝试所有模型，均失败")
                    raise
            except Exception as e:
                logger.error(f"调用模型 {self.model} 时发生未知错误: {str(e)}")
                
                # 切换到下一个模型
                logger.warning(f"模型 {self.model} 调用失败，尝试切换模型...")
                if self._switch_to_next_model():
                    retry_count += 1
                    continue
                else:
                    logger.error("已尝试所有模型，均失败")
                    raise
        
        logger.error("已尝试所有模型，均失败")
        raise Exception("已尝试所有模型，均失败")

    def get_focus_point(self, image_path: str) -> Dict[str, Any]:
        try:
            base64_image = self._encode_image(image_path)

            prompt = """Analyze this image and identify the main focus point. Return a JSON object with:
            - focus_point: {x, y} normalized coordinates (0-1) of the main focus
            - bbox: optional {x1, y1, x2, y2} normalized bounding box
            - shot_type: optional "closeup", "medium", or "long"
            - confidence: 0.0-1.0 confidence score
            - usable: boolean indicating if the image is clear and usable for training
            - reject_reason: reason if image is not usable (e.g., too_blurry, subject_not_clear)
            - reason: short reason for the focus point

            Only return valid JSON, no additional text."""

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
                                "url": base64_image
                            }
                        }
                    ]
                }
            ]

            response = self._call_model(messages)
            result = json.loads(response)
            
            # Validate the result
            if "focus_point" not in result:
                result["focus_point"] = {"x": 0.5, "y": 0.5}
                result["confidence"] = 0.0
            
            # Add default values for new fields
            if "usable" not in result:
                result["usable"] = True
            if "reject_reason" not in result:
                result["reject_reason"] = None
            
            # Normalize coordinates if needed
            for key in ["focus_point", "bbox"]:
                if key in result and result[key]:
                    for coord in result[key]:
                        result[key][coord] = max(0.0, min(1.0, result[key][coord]))
            
            return result
        except Exception as e:
            logger.error(f"Failed to get focus point: {str(e)}")
            # 返回默认结果作为回退
            return {
                "focus_point": {"x": 0.5, "y": 0.5},
                "bbox": {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0},
                "shot_type": "medium",
                "confidence": 0.0,
                "usable": False,
                "reject_reason": "failed_to_call_model",
                "reason": "failed to call model, using default focus point"
            }

    def generate_tags(self, image_path: str) -> Dict[str, Any]:
        try:
            base64_image = self._encode_image(image_path)

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

            messages = [
                {
                    "role": "system",
                    "content": "You are a professional image tagger. Generate concise, relevant tags and caption."
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
                                "url": base64_image
                            }
                        }
                    ]
                }
            ]

            response = self._call_model(messages)
            # 解析JSON响应
            result = json.loads(response)
            return result
        except Exception as e:
            logger.error(f"Failed to generate tags: {str(e)}")
            # 返回默认结果作为回退
            return {
                "caption": "unknown person, portrait",
                "tags": ["person", "portrait", "unknown"],
                "has_face": True,
                "shot_type": "medium",
                "notes": "failed to call model, using default tags"
            }

    def generate_caption(self, image_path: str, prompt: Optional[str] = None) -> str:
        """
        Generate long-form caption text for the final dataset packaging.
        """
        try:
            base64_image = self._encode_image(image_path)
            caption_prompt = prompt or DEFAULT_CAPTION_PROMPT

            messages = [
                {
                    "role": "system",
                    "content": "You are a precise dataset captioner for portrait/cosplay photos. Avoid speculation and keep concise."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": caption_prompt},
                        {"type": "image_url", "image_url": {"url": base64_image}},
                    ],
                },
            ]

            response = self._call_model(messages)
            return response.strip()
        except Exception as exc:
            logger.error(f"Failed to generate caption: {exc}")
            return "portrait photo, clean background, soft light\ntags: portrait,photo,soft light"
