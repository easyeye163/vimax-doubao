"""Doubao Seedream Image Generation API Adapter.

Supports text-to-image generation via ByteDance Doubao Ark API.
"""
import base64
import json
import logging
import os
from pathlib import Path
from typing import List, Optional

import requests

from interfaces.video_output import ImageOutput
from utils.image import image_path_to_b64

logger = logging.getLogger(__name__)


class ImageGeneratorDoubaoAPI:
    """Image generation using Doubao Seedream API."""

    def __init__(
        self,
        api_key: str,
        model: str = "doubao-seedream-3-0-t2i-250415",
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.image_url = f"{self.base_url}/images/generations"

    def _resolve_image_ref(self, reference_image_paths: Optional[List[str]]) -> Optional[str]:
        """Resolve reference image paths to data URIs or URLs."""
        if not reference_image_paths:
            return None
        path = reference_image_paths[0]
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return image_path_to_b64(path)

    def generate_single_image(
        self,
        prompt: str,
        reference_image_paths: Optional[List[str]] = None,
        size: str = "1024x1024",
        **kwargs
    ) -> ImageOutput:
        """Generate a single image.

        Args:
            prompt: Text prompt for image generation.
            reference_image_paths: Optional reference image(s) for image-to-image.
            size: Output image size (e.g., "1024x1024").

        Returns:
            ImageOutput containing the generated image.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }

        # If reference image provided, add as image_url content
        ref_url = self._resolve_image_ref(reference_image_paths)
        if ref_url:
            payload["image"] = ref_url

        logger.info(f"Generating image with model={self.model}, size={size}")
        resp = requests.post(self.image_url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if "data" in data and len(data["data"]) > 0:
            item = data["data"][0]
            if item.get("url"):
                return ImageOutput(fmt="url", ext="png", data=item["url"])
            elif item.get("b64_json"):
                return ImageOutput(fmt="base64", ext="png", data=item["b64_json"])

        raise ValueError(f"Unexpected response: {json.dumps(data, ensure_ascii=False)[:500]}")
