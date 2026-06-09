"""
ViMax-Doubao: Main Entry Point

Agentic Video Generation powered by ByteDance Doubao Seedance.
Idea → Story → Script → Images → Video
"""
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipelines.idea2video_pipeline import Idea2VideoPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def resolve_api_key():
    """Resolve API key from environment variable."""
    key = os.environ.get("DOUBAO_API_KEY", "")
    if not key:
        raise ValueError(
            "Please set DOUBAO_API_KEY environment variable.\n"
            "Example: export DOUBAO_API_KEY='your-ark-api-key'"
        )
    return key


def main():
    api_key = resolve_api_key()

    # ---- User Configuration ----
    idea = "一个女孩在海边看日出，随着音乐起舞，镜头从远景慢慢推进到特写"
    user_requirement = "3个场景，竖屏短视频风格，电影质感"
    style = "cinematic music video, golden hour lighting, soft warm tones"
    reference_image = None  # Path to reference image, or None
    chaining_mode = "ti2vid"  # "none" or "ti2vid"
    video_width = 768
    video_height = 1152
    # ---------------------------

    pipeline = Idea2VideoPipeline(
        api_key=api_key,
        video_duration=5,
        video_width=video_width,
        video_height=video_height,
        working_dir=".working_dir/idea2video",
    )

    final_video = pipeline.run(
        idea=idea,
        user_requirement=user_requirement,
        style=style,
        reference_image=reference_image,
        chaining_mode=chaining_mode,
        video_width=video_width,
        video_height=video_height,
    )

    if final_video:
        print(f"\n=== DONE === Final video: {final_video}")
    else:
        print("\n=== FAILED === Video generation did not complete.")


if __name__ == "__main__":
    main()
