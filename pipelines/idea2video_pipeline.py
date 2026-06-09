"""
Idea-to-Video Pipeline for ViMax-Doubao.

Orchestrates the full workflow:
1. Story Development (LLM)
2. Script Writing (LLM)
3. Character Reference Image Generation
4. Scene Video Generation (Doubao Seedance)
5. Video Concatenation (moviepy)
"""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import yaml

from agents.screenwriter import Screenwriter
from interfaces.video_output import ImageOutput, VideoOutput
from tools.image_generator_doubao_api import ImageGeneratorDoubaoAPI
from tools.video_generator_doubao_api import VideoGeneratorDoubaoAPI

logger = logging.getLogger(__name__)


class Idea2VideoPipeline:
    """Main pipeline for converting ideas into videos using Doubao Seedance."""

    def __init__(
        self,
        api_key: str,
        chat_model: str = "doubao-1-5-pro-32k",
        image_model: str = "doubao-seedream-3-0-t2i-250415",
        video_model: str = "doubao-seedance-1-5-pro-251215",
        video_duration: int = 5,
        video_width: int = 768,
        video_height: int = 1152,
        working_dir: str = ".working_dir/idea2video",
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    ):
        self.api_key = api_key
        self.video_duration = video_duration
        self.video_width = video_width
        self.video_height = video_height
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.screenwriter = Screenwriter(api_key=api_key, model=chat_model, base_url=base_url)
        self.image_gen = ImageGeneratorDoubaoAPI(api_key=api_key, model=image_model, base_url=base_url)
        self.video_gen = VideoGeneratorDoubaoAPI(
            api_key=api_key, model=video_model, base_url=base_url, default_duration=video_duration
        )

    @classmethod
    def init_from_config(cls, config_path: str = "configs/idea2video.yaml"):
        """Create pipeline from YAML config file."""
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Resolve API key from env or config
        api_key = os.environ.get("DOUBAO_API_KEY", "")
        config_key = config.get("api_key", "")
        if config_key.startswith("${") and config_key.endswith("}"):
            env_var = config_key[2:-1]
            api_key = os.environ.get(env_var, api_key)

        if not api_key:
            raise ValueError("API key not found. Set DOUBAO_API_KEY env var or api_key in config.")

        chat_cfg = config.get("chat_model", {}).get("init_args", {})
        img_cfg = config.get("image_generator", {}).get("init_args", {})
        vid_cfg = config.get("video_generator", {}).get("init_args", {})

        return cls(
            api_key=api_key,
            chat_model=chat_cfg.get("model", "doubao-1-5-pro-32k"),
            image_model=img_cfg.get("model", "doubao-seedream-3-0-t2i-250415"),
            video_model=vid_cfg.get("model", "doubao-seedance-1-5-pro-251215"),
            video_duration=vid_cfg.get("default_duration", 5),
            working_dir=config.get("working_dir", ".working_dir/idea2video"),
        )

    def _get_character_reference(self, story: dict, style: str, user_reference: Optional[str] = None) -> str:
        """Get or generate a character reference image."""
        ref_path = str(self.working_dir / "character_reference.png")

        if user_reference and os.path.exists(user_reference):
            logger.info(f"Using user-provided reference image: {user_reference}")
            return user_reference

        # Check cache
        if os.path.exists(ref_path):
            logger.info(f"Using cached character reference: {ref_path}")
            return ref_path

        # Generate character description and image
        char_desc = self.screenwriter.extract_character_description(story, style)
        logger.info(f"Character description: {char_desc[:200]}")

        img_out = self.image_gen.generate_single_image(
            prompt=char_desc,
            size="1024x1024",
        )
        saved_path = img_out.save(ref_path)
        return saved_path

    def _extract_last_frame(self, video_path: str, output_path: str) -> str:
        """Extract the last frame from a video using ffmpeg."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-sseof", "-0.1", "-i", video_path,
            "-frames:v", "1", "-q:v", "2", output_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=60, check=True)
            logger.info(f"Extracted last frame to {output_path}")
            return output_path
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Failed to extract last frame: {e}")
            return ""

    def _generate_chained_scenes(self, scenes: List[str], reference_image: str):
        """Generate videos with ti2vid chaining: each scene uses the last frame of the previous as input."""
        video_paths = []
        last_frame_path = reference_image

        for i, scene_prompt in enumerate(scenes):
            logger.info(f"=== Generating scene {i+1}/{len(scenes)} ===")
            scene_dir = self.working_dir / f"scene_{i:02d}"
            scene_dir.mkdir(parents=True, exist_ok=True)
            video_path = str(scene_dir / "video.mp4")

            # Use last frame as reference for ti2vid
            ref_images = [last_frame_path] if last_frame_path else None

            try:
                video_out = self.video_gen.generate_single_video(
                    prompt=scene_prompt,
                    reference_image_paths=ref_images,
                    duration=self.video_duration,
                )
                saved_path = video_out.save(video_path)
                video_paths.append(saved_path)

                # Extract last frame for next scene
                next_frame = str(scene_dir / "last_frame.png")
                extracted = self._extract_last_frame(saved_path, next_frame)
                if extracted:
                    last_frame_path = extracted

            except Exception as e:
                logger.error(f"Failed to generate scene {i+1}: {e}")
                # Fallback to text-to-video without reference
                try:
                    video_out = self.video_gen.generate_single_video(
                        prompt=scene_prompt,
                        duration=self.video_duration,
                    )
                    saved_path = video_out.save(video_path)
                    video_paths.append(saved_path)
                except Exception as e2:
                    logger.error(f"Scene {i+1} fallback also failed: {e2}")

        return video_paths

    def _concatenate_videos(self, video_paths: List[str], output_path: str):
        """Concatenate multiple video clips into one final video using ffmpeg."""
        if not video_paths:
            logger.warning("No videos to concatenate.")
            return

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Create concat file
        concat_file = str(self.working_dir / "concat_list.txt")
        with open(concat_file, "w") as f:
            for vp in video_paths:
                f.write(f"file '{vp}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file, "-c", "copy", output_path
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=120, check=True)
            logger.info(f"Final video saved to {output_path}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"Failed to concatenate videos: {e}")
            # Try moviepy fallback
            try:
                from moviepy.editor import VideoFileClip, concatenate_videoclips
                clips = [VideoFileClip(vp) for vp in video_paths if os.path.exists(vp)]
                if clips:
                    final = concatenate_videoclips(clips, method="compose")
                    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
                    final.close()
                    logger.info(f"Final video saved via moviepy to {output_path}")
            except Exception as e2:
                logger.error(f"Moviepy fallback also failed: {e2}")

    def run(
        self,
        idea: str,
        user_requirement: str = "",
        style: str = "cinematic",
        reference_image: Optional[str] = None,
        chaining_mode: str = "ti2vid",
        video_width: int = 0,
        video_height: int = 0,
    ) -> Optional[str]:
        """Run the full idea-to-video pipeline.

        Args:
            idea: The core idea/concept for the video.
            user_requirement: Additional requirements (e.g., "3 scenes, portrait").
            style: Visual style (e.g., "cinematic", "anime", "documentary").
            reference_image: Path to a reference image for character consistency.
            chaining_mode: "none" (independent scenes) or "ti2vid" (chained).
            video_width: Override video width.
            video_height: Override video height.

        Returns:
            Path to the final concatenated video, or None on failure.
        """
        w = video_width or self.video_width
        h = video_height or self.video_height

        logger.info(f"=== ViMax-Doubao Pipeline ===")
        logger.info(f"Idea: {idea[:100]}...")
        logger.info(f"Style: {style}, Chaining: {chaining_mode}")
        logger.info(f"Resolution: {w}x{h}")

        # Step 1: Develop story
        story_path = str(self.working_dir / "story.json")
        if os.path.exists(story_path):
            with open(story_path) as f:
                story = json.load(f)
            logger.info("Loaded cached story")
        else:
            story = self.screenwriter.develop_story(idea, user_requirement, style)
            with open(story_path, "w") as f:
                json.dump(story, f, ensure_ascii=False, indent=2)
            logger.info(f"Story: {story.get('title', 'Untitled')}")

        # Step 2: Write script
        script_path = str(self.working_dir / "script.json")
        if os.path.exists(script_path):
            with open(script_path) as f:
                scenes = json.load(f)
            logger.info("Loaded cached script")
        else:
            scenes = self.screenwriter.write_script(story, user_requirement, style)
            with open(script_path, "w") as f:
                json.dump(scenes, f, ensure_ascii=False, indent=2)
            logger.info(f"Script: {len(scenes)} scenes")

        # Step 3: Character reference
        char_ref = self._get_character_reference(story, style, reference_image)

        # Step 4: Generate scene videos
        if chaining_mode == "ti2vid":
            video_paths = self._generate_chained_scenes(scenes, char_ref)
        else:
            # Independent scenes (no chaining)
            video_paths = []
            for i, scene_prompt in enumerate(scenes):
                scene_dir = self.working_dir / f"scene_{i:02d}"
                scene_dir.mkdir(parents=True, exist_ok=True)
                video_path = str(scene_dir / "video.mp4")
                try:
                    video_out = self.video_gen.generate_single_video(
                        prompt=scene_prompt,
                        reference_image_paths=[char_ref],
                        duration=self.video_duration,
                    )
                    video_paths.append(video_out.save(video_path))
                except Exception as e:
                    logger.error(f"Scene {i+1} failed: {e}")

        # Step 5: Concatenate
        if len(video_paths) > 1:
            final_path = str(self.working_dir / "final_video.mp4")
            self._concatenate_videos(video_paths, final_path)
            return final_path
        elif len(video_paths) == 1:
            return video_paths[0]
        else:
            logger.error("No videos were generated!")
            return None

    def __call__(self, *args, **kwargs):
        """Alias for run()."""
        return self.run(*args, **kwargs)
