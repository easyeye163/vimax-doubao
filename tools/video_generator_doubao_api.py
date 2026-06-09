"""Doubao Seedance Video Generation API Adapter.

Supports text-to-video and image-to-video via ByteDance Doubao Seedance API.

API Endpoints:
- POST /api/v3/contents/generations/tasks  - Create video generation task
- GET  /api/v3/contents/generations/tasks/{id}  - Query task status
"""
import json
import logging
import time
from typing import List, Optional

import requests

from interfaces.video_output import VideoOutput
from utils.image import image_path_to_b64

logger = logging.getLogger(__name__)


class VideoGeneratorDoubaoAPI:
    """Video generation using Doubao Seedance API (async task-based)."""

    # Duration presets
    DURATION_PRESETS = {
        5: {"duration": 5},
        10: {"duration": 10},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "doubao-seedance-1-5-pro-251215",
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        default_duration: int = 5,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.task_url = f"{self.base_url}/contents/generations/tasks"
        self.default_duration = default_duration

    def _resolve_image_ref(self, image_path: str) -> str:
        """Resolve an image path to a URL or data URI."""
        if image_path.startswith("http://") or image_path.startswith("https://"):
            return image_path
        return image_path_to_b64(image_path)

    def _build_content(self, prompt: str, image_paths: Optional[List[str]], duration: int,
                       camerafixed: bool = False, watermark: bool = True, seed: Optional[int] = None) -> list:
        """Build the content array for the API request."""
        content = []

        # Append prompt parameters
        full_prompt = f"{prompt} --duration {duration} --camerafixed {str(camerafixed).lower()} --watermark {str(watermark).lower()}"
        if seed is not None:
            full_prompt += f" --seed {seed}"

        content.append({
            "type": "text",
            "text": full_prompt
        })

        # Append reference image(s) if provided
        if image_paths:
            for img_path in image_paths:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": self._resolve_image_ref(img_path)
                    }
                })

        return content

    def _submit_task(self, content: list) -> str:
        """Submit a video generation task and return the task ID."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "content": content,
        }

        logger.info(f"Submitting video task with model={self.model}")
        resp = requests.post(self.task_url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        task_id = data.get("id")
        if not task_id:
            raise ValueError(f"No task ID in response: {json.dumps(data, ensure_ascii=False)[:500]}")

        logger.info(f"Task submitted: id={task_id}")
        return task_id

    def _poll_task(self, task_id: str, poll_interval: int = 15, timeout: int = 900) -> dict:
        """Poll a task until completion or timeout.

        Returns:
            The full task response dict with video URL on success.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        query_url = f"{self.task_url}/{task_id}"

        start_time = time.time()
        last_progress = -1

        while time.time() - start_time < timeout:
            resp = requests.get(query_url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status", "unknown")
            progress = data.get("progress", -1)

            if progress != last_progress:
                logger.info(f"Task {task_id}: status={status}, progress={progress}%")
                last_progress = progress

            if status == "succeeded" or status == "completed":
                return data
            elif status == "failed":
                error_msg = data.get("error", {}).get("message", "Unknown error")
                raise RuntimeError(f"Task {task_id} failed: {error_msg}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

    def _extract_video_url(self, task_result: dict) -> str:
        """Extract the video URL from a completed task result."""
        # Doubao returns video content in the content array
        content = task_result.get("content", [])
        for item in content:
            if item.get("type") == "video_url" or item.get("type") == "video":
                video_url = item.get("video_url", {}).get("url", "")
                if not video_url:
                    video_url = item.get("url", "")
                if video_url:
                    return video_url

        # Try alternative response formats
        if "output" in task_result:
            output = task_result["output"]
            if isinstance(output, dict) and "video_url" in output:
                return output["video_url"]

        raise ValueError(f"Cannot extract video URL from task result: {json.dumps(task_result, ensure_ascii=False)[:500]}")

    def generate_single_video(
        self,
        prompt: str,
        reference_image_paths: Optional[List[str]] = None,
        duration: int = 0,
        width: int = 768,
        height: int = 1152,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
        **kwargs
    ) -> VideoOutput:
        """Generate a single video.

        Supports:
        - Text-to-video (no reference images)
        - Image-to-video (ti2vid, 1 reference image)

        Args:
            prompt: Text prompt describing the video.
            reference_image_paths: Reference image(s) for image-to-video.
            duration: Video duration in seconds (0 = use default).
            width: Target video width.
            height: Target video height.
            seed: Random seed for reproducibility.
            negative_prompt: Negative prompt (not supported by all models).

        Returns:
            VideoOutput containing the generated video.
        """
        if duration <= 0:
            duration = self.default_duration

        # Build content for the API
        content = self._build_content(
            prompt=prompt,
            image_paths=reference_image_paths,
            duration=duration,
            seed=seed,
        )

        # Submit and poll
        task_id = self._submit_task(content)
        task_result = self._poll_task(task_id)

        # Extract video URL
        video_url = self._extract_video_url(task_result)
        logger.info(f"Video generated: {video_url[:100]}...")

        return VideoOutput(fmt="url", ext="mp4", data=video_url)
