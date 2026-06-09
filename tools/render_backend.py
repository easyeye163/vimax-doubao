"""Render backend factory - initializes generators from config."""
import importlib
from typing import Any

from tools.protocols import ImageGenerator, VideoGenerator


class RenderBackend:
    """Factory that creates image and video generator instances from config."""

    def __init__(self, config: dict, api_key: str):
        self.image_gen = self._create_generator(
            config.get("image_generator", {}), api_key, ImageGenerator
        )
        self.video_gen = self._create_generator(
            config.get("video_generator", {}), api_key, VideoGenerator
        )

    def _create_generator(self, gen_config: dict, api_key: str, protocol):
        """Dynamically import and instantiate a generator class."""
        class_path = gen_config.get("class_path", "")
        if not class_path:
            raise ValueError(f"Missing class_path in generator config: {gen_config}")

        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)

        init_args = gen_config.get("init_args", {})
        init_args["api_key"] = api_key
        return cls(**init_args)
