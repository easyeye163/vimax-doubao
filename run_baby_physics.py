#!/usr/bin/env python3
"""
run_baby_physics.py - 可爱宝宝学物理 5场景50秒视频

Uses Doubao Seedance API via vimax-doubao framework.
5 scenes x 10s = 50s total
"""
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
API_KEY = "ark-9df311f6-cc22-4e40-9e36-40a92baa1b6e-012f2"
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
IMAGE_MODEL = "doubao-seedream-3-0-t2i-250415"
VIDEO_MODEL = "doubao-seedance-1-5-pro-251215"
VIDEO_DURATION = 10
WORKING_DIR = Path(".working_dir/baby_physics")

# 5 scenes: cute baby learning physics
SCENES = [
    # Scene 1: Baby playing with blocks, discovering gravity
    {
        "title": "积木塔倒塌 - 发现重力",
        "prompt": "A super cute 2-year-old baby with chubby cheeks sitting on a colorful play mat, "
                  "stacking wooden blocks into a tall tower. The baby looks excited and focused. "
                  "The tower wobbles and collapses, blocks scatter everywhere. "
                  "The baby looks surprised with big sparkling eyes, then giggles and claps hands. "
                  "Warm soft lighting, pastel colors, cozy nursery room background. "
                  "Slow motion on the tower falling. Cinematic, adorable, high quality.",
        "image_prompt": None,  # will use character ref
    },
    # Scene 2: Baby watching a ball roll down a ramp
    {
        "title": "小球滚下斜坡 - 惯性与运动",
        "prompt": "A super cute 2-year-old baby sitting on the floor, watching a bright red rubber ball "
                  "roll down a wooden ramp. The baby's eyes follow the ball with wonder and curiosity. "
                  "The baby then pushes the ball back up the ramp, watching it roll down again. "
                  "Scientific wonder on the baby's face, mouth slightly open in amazement. "
                  "Bright nursery with educational toys in background. Warm afternoon sunlight through window. "
                  "Smooth camera tracking the ball movement.",
        "image_prompt": None,
    },
    # Scene 3: Baby playing with magnets
    {
        "title": "磁铁吸住玩具 - 神奇的力量",
        "prompt": "A super cute 2-year-old baby holding a colorful magnet wand, "
                  "discovering it can attract metal objects. The baby waves the wand near paper clips "
                  "and small metal toys, watching them magically stick to the magnet. "
                  "The baby looks absolutely amazed, eyes wide open, letting out a delighted gasp. "
                  "Close-up on the baby's adorable amazed expression. "
                  "Soft bokeh background with colorful nursery decorations. Magical warm lighting.",
        "image_prompt": None,
    },
    # Scene 4: Baby watching water float/sink objects in a basin
    {
        "title": "水盆实验 - 浮与沉",
        "prompt": "A super cute 2-year-old baby standing at a small plastic basin filled with water, "
                  "dropping different objects into the water. A wooden toy floats while a small metal spoon sinks. "
                  "The baby pokes the floating toy with tiny fingers, watching it bob up and down. "
                  "Water splashes gently, the baby laughs with pure joy. "
                  "Sunlit bathroom setting, water droplets glistening. "
                  "Slow motion water ripples. Adorable, cinematic, warm tones.",
        "image_prompt": None,
    },
    # Scene 5: Baby looking through a prism, seeing rainbow colors
    {
        "title": "三棱镜彩虹 - 光的魔法",
        "prompt": "A super cute 2-year-old baby holding a glass prism up to a beam of sunlight, "
                  "creating a beautiful rainbow spectrum on the wall. The baby turns the prism slowly, "
                  "watching the rainbow colors dance across the wall. "
                  "The baby reaches out trying to touch the rainbow light, giggling with delight. "
                  "Magical atmosphere, rainbow colors reflecting in the baby's eyes. "
                  "The baby looks like a little scientist discovering the world. "
                  "Golden hour lighting, dreamy bokeh background. breathtakingly beautiful.",
        "image_prompt": None,
    },
]

CHARACTER_PROMPT = (
    "A super cute 2-year-old Asian baby with round chubby cheeks, big sparkling dark eyes, "
    "short soft black hair, wearing a colorful striped onesie with tiny cartoon physics symbols. "
    "The baby has an adorable curious expression, sitting on a soft pastel play mat. "
    "Warm nursery setting with educational toys visible in background. "
    "Soft warm lighting, studio quality portrait, 8K resolution, hyper detailed, adorable."
)


def generate_image(prompt: str, size: str = "1024x1024") -> str:
    """Generate an image via Doubao Seedream."""
    logger.info(f"Generating image: {prompt[:80]}...")
    resp = requests.post(
        f"{BASE_URL}/images/generations",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": IMAGE_MODEL, "prompt": prompt, "size": size, "n": 1},
        timeout=120,
    )
    resp.raise_for_status()
    url = resp.json()["data"][0]["url"]
    logger.info(f"Image generated: {url[:80]}...")
    return url


def submit_video_task(prompt: str, image_url: str = None, duration: int = 10) -> str:
    """Submit a video generation task."""
    content = [{"type": "text", "text": f"{prompt} --duration {duration} --camerafixed false --watermark true"}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    resp = requests.post(
        f"{BASE_URL}/contents/generations/tasks",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": VIDEO_MODEL, "content": content},
        timeout=120,
    )
    resp.raise_for_status()
    task_id = resp.json().get("id")
    logger.info(f"Video task submitted: {task_id}")
    return task_id


def poll_video_task(task_id: str, timeout: int = 1200) -> dict:
    """Poll video task until complete."""
    url = f"{BASE_URL}/contents/generations/tasks/{task_id}"
    start = time.time()
    last_status = ""
    while time.time() - start < timeout:
        resp = requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "unknown")
        if status != last_status:
            logger.info(f"  Task {task_id}: status={status}")
            last_status = status
        if status in ("succeeded", "completed"):
            return data
        if status == "failed":
            raise RuntimeError(f"Task failed: {json.dumps(data, ensure_ascii=False)[:500]}")
        time.sleep(20)
    raise TimeoutError(f"Task {task_id} timed out after {timeout}s")


def extract_video_url(task_result: dict) -> str:
    """Extract video URL from task result."""
    for item in task_result.get("content", []):
        if item.get("type") in ("video_url", "video"):
            return item.get("video_url", {}).get("url", "") or item.get("url", "")
    # Try nested structures
    resp_output = task_result.get("output", {})
    if isinstance(resp_output, dict):
        video_url = resp_output.get("video_url", "") or resp_output.get("url", "")
        if video_url:
            return video_url
        # Check choices
        choices = task_result.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            for c in msg.get("content", []):
                if isinstance(c, dict):
                    if c.get("type") in ("video_url", "video"):
                        return c.get("video_url", {}).get("url", "") or c.get("url", "")
    raise ValueError(f"Cannot find video URL. Response: {json.dumps(task_result, ensure_ascii=False)[:500]}")


def download_file(url: str, path: str):
    """Download a file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)
    logger.info(f"Downloaded: {path}")


def extract_last_frame(video_path: str, output_path: str) -> bool:
    """Extract last frame from video using ffmpeg."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-sseof", "-0.1", "-i", video_path, "-frames:v", "1", "-q:v", "2", output_path],
            capture_output=True, timeout=60, check=True
        )
        return os.path.exists(output_path)
    except Exception as e:
        logger.warning(f"Failed to extract last frame: {e}")
        return False


def concatenate_videos(video_paths: list, output_path: str):
    """Concatenate videos with ffmpeg."""
    concat_file = str(WORKING_DIR / "concat.txt")
    with open(concat_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path],
        capture_output=True, timeout=120,
    )
    if result.returncode != 0:
        logger.error(f"ffmpeg concat failed: {result.stderr.decode()[:500]}")
        # Fallback with re-encode
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
             "-c:v", "libx264", "-preset", "fast", "-crf", "23", output_path],
            capture_output=True, timeout=300,
        )
    logger.info(f"Final video: {output_path}")


def main():
    WORKING_DIR.mkdir(parents=True, exist_ok=True)

    # Save state for resume
    state_file = WORKING_DIR / "state.json"

    # Step 1: Generate character reference image
    char_ref_path = str(WORKING_DIR / "character_reference.png")
    if not os.path.exists(char_ref_path):
        logger.info("=== Step 1: Generating character reference image ===")
        char_url = generate_image(CHARACTER_PROMPT)
        download_file(char_url, char_ref_path)
    else:
        logger.info("=== Step 1: Using cached character reference ===")

    # Step 2: Generate 5 scene videos
    video_paths = []
    last_frame_path = char_ref_path

    for i, scene in enumerate(SCENES):
        scene_dir = WORKING_DIR / f"scene_{i:02d}"
        video_path = str(scene_dir / "video.mp4")

        # Skip if already generated
        if os.path.exists(video_path) and os.path.getsize(video_path) > 10000:
            logger.info(f"=== Scene {i+1}/5: {scene['title']} (cached) ===")
            video_paths.append(video_path)
            frame_path = str(scene_dir / "last_frame.png")
            if os.path.exists(frame_path):
                last_frame_path = frame_path
            continue

        logger.info(f"=== Scene {i+1}/5: {scene['title']} ===")

        try:
            # Use last frame from previous scene for chaining
            ref = last_frame_path if last_frame_path else char_ref_path
            task_id = submit_video_task(scene["prompt"], image_url=ref, duration=VIDEO_DURATION)
            result = poll_video_task(task_id)
            vid_url = extract_video_url(result)
            download_file(vid_url, video_path)
            video_paths.append(video_path)

            # Extract last frame for next scene chaining
            frame_path = str(scene_dir / "last_frame.png")
            if extract_last_frame(video_path, frame_path):
                last_frame_path = frame_path

            # Save state
            state = {"completed_scenes": [j for j in range(i+1)], "video_paths": video_paths}
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.error(f"Scene {i+1} failed: {e}")
            # Save state for resume
            state = {"completed_scenes": [j for j in range(i)], "video_paths": video_paths, "error": str(e)}
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
            raise

    # Step 3: Concatenate all scenes
    logger.info("=== Step 3: Concatenating all scenes ===")
    final_path = str(WORKING_DIR / "baby_physics_50s.mp4")
    concatenate_videos(video_paths, final_path)

    # Get file size
    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    print(f"\n{'='*50}")
    print(f"VIDEO COMPLETE: {final_path}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Scenes: {len(video_paths)} x {VIDEO_DURATION}s = {len(video_paths)*VIDEO_DURATION}s")
    print(f"{'='*50}")

    return final_path


if __name__ == "__main__":
    result = main()
    if result:
        print(f"OUTPUT: {result}")
    else:
        print("FAILED")
        sys.exit(1)
