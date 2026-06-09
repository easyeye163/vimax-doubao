"""Protocol definitions for image and video generators."""
from typing import Protocol, List, Optional
from interfaces.video_output import ImageOutput, VideoOutput


class ImageGenerator(Protocol):
    """Protocol for image generation backends."""

    def generate_single_image(
        self,
        prompt: str,
        reference_image_paths: Optional[List[str]] = None,
        **kwargs
    ) -> ImageOutput:
        """Generate a single image from prompt, optionally with reference images."""
        ...


class VideoGenerator(Protocol):
    """Protocol for video generation backends."""

    def generate_single_video(
        self,
        prompt: str,
        reference_image_paths: Optional[List[str]] = None,
        duration: int = 5,
        width: int = 768,
        height: int = 1152,
        **kwargs
    ) -> VideoOutput:
        """Generate a single video from prompt, optionally with reference images."""
        ...
