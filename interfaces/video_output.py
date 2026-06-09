"""Output container classes for images and videos."""
from __future__ import annotations
import base64
import logging
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ImageOutput:
    """Container for a generated image (URL or base64)."""

    def __init__(self, fmt: str, ext: str, data: str):
        self.fmt = fmt       # "url" or "base64"
        self.ext = ext       # "png", "jpg", etc.
        self.data = data     # URL string or base64 string

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def save(self, path: str):
        """Download (if URL) or decode (if base64) and save to path."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        if self.fmt == "url":
            resp = requests.get(self.data, timeout=120)
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
        elif self.fmt == "base64":
            with open(path, "wb") as f:
                f.write(base64.b64decode(self.data))
        else:
            raise ValueError(f"Unknown format: {self.fmt}")

        logger.info(f"Image saved to {path}")
        return path


class VideoOutput:
    """Container for a generated video (URL or bytes)."""

    def __init__(self, fmt: str, ext: str, data):
        self.fmt = fmt       # "url", "base64", "bytes"
        self.ext = ext       # "mp4", etc.
        self.data = data     # URL string, base64 string, or bytes

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def save(self, path: str):
        """Download (if URL) or write (if bytes/base64) and save to path."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        if self.fmt == "url":
            resp = requests.get(self.data, timeout=300)
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
        elif self.fmt == "base64":
            with open(path, "wb") as f:
                f.write(base64.b64decode(self.data))
        elif self.fmt == "bytes":
            if isinstance(self.data, bytes):
                with open(path, "wb") as f:
                    f.write(self.data)
            else:
                raise TypeError("data must be bytes when fmt='bytes'")
        else:
            raise ValueError(f"Unknown format: {self.fmt}")

        logger.info(f"Video saved to {path}")
        return path
