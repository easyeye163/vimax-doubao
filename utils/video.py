"""Video download utilities."""
import logging
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def download_video(url: str, save_path: str) -> str:
    """Download a video from URL and save locally."""
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)
    logger.info(f"Downloaded video to {save_path}")
    return save_path
