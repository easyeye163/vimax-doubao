"""Image download and conversion utilities."""
import base64
import logging
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def download_image(url: str, save_path: str) -> str:
    """Download an image from URL and save locally."""
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)
    logger.info(f"Downloaded image to {save_path}")
    return save_path


def image_path_to_b64(image_path: str) -> str:
    """Convert a local image file to base64 data URI."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    ext = Path(image_path).suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
    return f"data:{mime};base64,{b64}"
