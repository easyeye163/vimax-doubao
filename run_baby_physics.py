#!/usr/bin/env python3
"""
run_baby_physics.py - 可爱宝宝学物理 5场景50秒视频 (v2)

Improvements over v1:
1. Per-scene first-frame: each scene gets a unique first-frame image
   generated via i2i from the character reference, keeping the baby consistent
   but placing them in different scene contexts.
2. Model fallback: if doubao-seedance-1-5-pro fails (e.g., insufficient balance),
   automatically falls back to doubao-seedance-1-0-pro-fast-251015.

Uses Doubao Seedance API via vimax-doubao framework.
5 scenes x 10s = 50s total
"""
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
API_KEY = os.environ.get("DOUBAO_API_KEY", "ark-9df311f6-cc22-4e40-9e36-40a92baa1b6e-012f2")
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
IMAGE_MODEL = "doubao-seedream-5-0-260128"
VIDEO_MODEL_PRIMARY = "doubao-seedance-1-5-pro-251215"
VIDEO_MODEL_FALLBACK = "doubao-seedance-1-0-pro-fast-251015"
VIDEO_DURATION = 10
WORKING_DIR = Path(".working_dir/baby_physics_v2")

# 5 scenes: cute baby learning physics
# Each scene has its own first-frame image prompt (same baby, different setting)
SCENES = [
    {
        "title": "积木塔倒塌 - 发现重力",
        "video_prompt": "A super cute 2-year-old baby with chubby cheeks sitting on a colorful play mat, "
                       "stacking wooden blocks into a tall tower. The baby looks excited and focused. "
                       "The tower wobbles and collapses, blocks scatter everywhere. "
                       "The baby looks surprised with big sparkling eyes, then giggles and claps hands. "
                       "Warm soft lighting, pastel colors, cozy nursery room. "
                       "Slow motion on the tower falling. Cinematic adorable high quality.",
        "first_frame_prompt": "A super cute 2-year-old Asian baby with round chubby cheeks and big sparkling "
                              "dark eyes, sitting on a colorful play mat in a cozy nursery room, "
                              "reaching out to place a wooden block on top of a stack. "
                              "The baby wears a colorful striped onesie. Warm soft lighting, pastel colors, "
                              "wooden blocks scattered around, educational toys in background. Studio quality, 8K.",
    },
    {
        "title": "小球滚下斜坡 - 惯性与运动",
        "video_prompt": "A super cute 2-year-old baby sitting on the floor, watching a bright red rubber ball "
                       "roll down a wooden ramp. The baby's eyes follow the ball with wonder and curiosity. "
                       "The baby then pushes the ball back up the ramp, watching it roll down again. "
                       "Scientific wonder on baby's face, mouth slightly open. "
                       "Bright nursery, warm afternoon sunlight through window. "
                       "Smooth camera tracking the ball movement.",
        "first_frame_prompt": "A super cute 2-year-old Asian baby with round chubby cheeks and big sparkling "
                              "dark eyes, sitting on the floor of a bright nursery, watching a red rubber ball "
                              "on a wooden ramp with curiosity. The baby wears a colorful striped onesie. "
                              "Afternoon sunlight streaming through window, educational toys in background. "
                              "Warm golden lighting, studio quality, 8K.",
    },
    {
        "title": "磁铁吸住玩具 - 神奇的力量",
        "video_prompt": "A super cute 2-year-old baby holding a colorful magnet wand, "
                       "discovering it can attract metal objects. The baby waves the wand near paper clips "
                       "and small metal toys, watching them magically stick. "
                       "The baby looks absolutely amazed, eyes wide open, delighted gasp. "
                       "Close-up on baby's adorable amazed expression. "
                       "Soft bokeh background, colorful nursery. Magical warm lighting.",
        "first_frame_prompt": "A super cute 2-year-old Asian baby with round chubby cheeks and big sparkling "
                              "dark eyes, holding a colorful magnet wand in tiny hands, eyes wide with amazement "
                              "as metal paper clips stick to the wand. The baby wears a colorful striped onesie. "
                              "Soft bokeh background with colorful nursery decorations, magical warm lighting. "
                              "Close-up portrait, studio quality, 8K.",
    },
    {
        "title": "水盆实验 - 浮与沉",
        "video_prompt": "A super cute 2-year-old baby standing at a small plastic basin filled with water, "
                       "dropping different objects into the water. A wooden toy floats while a metal spoon sinks. "
                       "The baby pokes the floating toy with tiny fingers, watching it bob. "
                       "Water splashes gently, baby laughs with pure joy. "
                       "Sunlit bathroom, water droplets glistening. "
                       "Slow motion water ripples. Adorable cinematic warm tones.",
        "first_frame_prompt": "A super cute 2-year-old Asian baby with round chubby cheeks and big sparkling "
                              "dark eyes, standing at a small plastic basin filled with water, reaching out to "
                              "drop a wooden toy into the water. The baby wears a colorful striped onesie rolled "
                              "up at the sleeves. Sunlit bathroom, water droplets glistening, toy floating. "
                              "Warm cinematic lighting, studio quality, 8K.",
    },
    {
        "title": "三棱镜彩虹 - 光的魔法",
        "video_prompt": "A super cute 2-year-old baby holding a glass prism up to a beam of sunlight, "
                       "creating a beautiful rainbow spectrum on the wall. The baby turns the prism slowly, "
                       "watching rainbow colors dance across the wall. "
                       "The baby reaches out trying to touch the rainbow light, giggling. "
                       "Magical atmosphere, rainbow colors in baby's eyes. "
                       "Golden hour lighting, dreamy bokeh. breathtakingly beautiful.",
        "first_frame_prompt": "A super cute 2-year-old Asian baby with round chubby cheeks and big sparkling "
                              "dark eyes, holding a glass prism up toward a beam of golden sunlight, "
                              "a rainbow spectrum visible on the wall behind. The baby wears a colorful striped "
                              "onesie. Magical atmosphere, rainbow colors reflecting in baby's eyes. "
                              "Golden hour lighting, dreamy bokeh background. Studio quality, 8K.",
    },
]

# Shared character description for consistent identity across scenes
CHARACTER_REF_PROMPT = (
    "A super cute 2-year-old Asian baby with round chubby cheeks, big sparkling dark eyes, "
    "short soft black hair, wearing a colorful striped onesie with tiny cartoon physics symbols. "
    "The baby has an adorable curious expression. "
    "Warm nursery setting, soft warm lighting, studio quality portrait, 8K resolution, hyper detailed."
)


# ============ API HELPERS ============

def generate_image_t2i(prompt: str, size: str = "2048x2048") -> str:
    """Text-to-image generation via Doubao Seedream."""
    logger.info(f"[IMG t2i] {prompt[:80]}...")
    resp = requests.post(
        f"{BASE_URL}/images/generations",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": IMAGE_MODEL, "prompt": prompt, "size": size, "n": 1},
        timeout=120,
    )
    resp.raise_for_status()
    url = resp.json()["data"][0]["url"]
    logger.info(f"[IMG] Generated: {url[:80]}...")
    return url


def generate_image_i2i(prompt: str, reference_url: str, size: str = "2048x2048") -> str:
    """Image-to-image generation: use reference to maintain character consistency."""
    logger.info(f"[IMG i2i] {prompt[:80]}...")
    resp = requests.post(
        f"{BASE_URL}/images/generations",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "image": reference_url,
            "size": size,
            "n": 1,
        },
        timeout=120,
    )
    resp.raise_for_status()
    url = resp.json()["data"][0]["url"]
    logger.info(f"[IMG i2i] Generated: {url[:80]}...")
    return url


def submit_video_task(prompt: str, image_url: str = None, duration: int = 10) -> tuple:
    """Submit a video generation task with model fallback.

    Returns (task_id, model_used).
    """
    content = [{"type": "text", "text": f"{prompt} --duration {duration} --camerafixed false --watermark true"}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    models = [VIDEO_MODEL_PRIMARY, VIDEO_MODEL_FALLBACK]
    last_error = None

    for model in models:
        try:
            logger.info(f"[VID] Submitting with model={model}")
            resp = requests.post(
                f"{BASE_URL}/contents/generations/tasks",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={"model": model, "content": content},
                timeout=120,
            )

            if resp.status_code >= 400:
                error_data = resp.json() if "json" in resp.headers.get("content-type", "") else {}
                error_msg = error_data.get("error", {}).get("message", "")
                error_code = error_data.get("error", {}).get("code", "")
                logger.warning(f"[VID] {model} failed: {error_code} - {error_msg}")

                # Check if it's a balance/quota error -> fallback
                err_lower = error_msg.lower()
                if any(kw in err_lower for kw in ("balance", "quota", "insufficient", "limit", "resource")):
                    logger.info(f"[VID] Falling back to next model...")
                    last_error = f"{error_code}: {error_msg}"
                    continue
                else:
                    raise RuntimeError(f"Task submit failed: {error_code}: {error_msg}")

            resp.raise_for_status()
            task_id = resp.json().get("id")
            logger.info(f"[VID] Task submitted: {task_id} (model={model})")
            return task_id, model

        except RuntimeError:
            raise

    raise RuntimeError(f"All video models failed. Last: {last_error}")


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
            logger.info(f"[VID] Task {task_id}: status={status}")
            last_status = status
        if status in ("succeeded", "completed"):
            return data
        if status == "failed":
            raise RuntimeError(f"Task failed: {json.dumps(data, ensure_ascii=False)[:500]}")
        time.sleep(20)
    raise TimeoutError(f"Task {task_id} timed out after {timeout}s")


def extract_video_url(task_result: dict) -> str:
    """Extract video URL from Doubao task result (content is a dict)."""
    content = task_result.get("content", {})
    if isinstance(content, dict):
        video_url = content.get("video_url", "")
        if video_url:
            return video_url
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") in ("video_url", "video"):
                return item.get("video_url", {}).get("url", "") or item.get("url", "")
    raise ValueError(f"No video URL found. Response: {json.dumps(task_result, ensure_ascii=False)[:500]}")


def download_file(url: str, path: str):
    """Download a file from URL."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)
    size_mb = os.path.getsize(path) / (1024 * 1024)
    logger.info(f"[DL] {path} ({size_mb:.1f}MB)")


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
        logger.error(f"ffmpeg concat failed, re-encoding...")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
             "-c:v", "libx264", "-preset", "fast", "-crf", "23", output_path],
            capture_output=True, timeout=300,
        )


# ============ MAIN PIPELINE ============

def main():
    WORKING_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Step 1: Generate character reference image ----
    char_ref_path = str(WORKING_DIR / "character_reference.png")
    char_ref_url = None

    if os.path.exists(char_ref_path):
        logger.info("=== Step 1: Using cached character reference ===")
    else:
        logger.info("=== Step 1: Generating character reference image ===")
        char_ref_url = generate_image_t2i(CHARACTER_REF_PROMPT)
        download_file(char_ref_url, char_ref_path)

    # Upload char ref to get a usable URL (for Doubao i2i)
    # If we just generated it, use the URL directly
    if not char_ref_url:
        # For cached ref, we need a public URL - use Agnes as proxy
        import base64
        with open(char_ref_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        # Try Doubao i2i with base64
        char_ref_url = f"data:image/png;base64,{b64}"

    # ---- Step 2: Generate per-scene first-frame images (i2i for consistency) ----
    scene_first_frames = []
    for i, scene in enumerate(SCENES):
        frame_path = str(WORKING_DIR / f"scene_{i:02d}" / "first_frame.png")
        scene_dir = WORKING_DIR / f"scene_{i:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)

        if os.path.exists(frame_path):
            logger.info(f"=== Step 2.{i+1}: Scene {i+1} first-frame (cached) ===")
            scene_first_frames.append(frame_path)
            continue

        logger.info(f"=== Step 2.{i+1}: Generating Scene {i+1} first-frame ({scene['title']}) ===")
        try:
            frame_url = generate_image_i2i(scene["first_frame_prompt"], char_ref_url)
            download_file(frame_url, frame_path)
            scene_first_frames.append(frame_path)
        except Exception as e:
            logger.warning(f"Scene {i+1} first-frame generation failed: {e}, will use char ref as fallback")
            scene_first_frames.append(char_ref_path)

    # ---- Step 3: Generate 5 scene videos (each with unique first-frame) ----
    video_paths = []

    for i, scene in enumerate(SCENES):
        video_path = str(WORKING_DIR / f"scene_{i:02d}" / "video.mp4")

        if os.path.exists(video_path) and os.path.getsize(video_path) > 10000:
            logger.info(f"=== Scene {i+1}/5: {scene['title']} (cached) ===")
            video_paths.append(video_path)
            continue

        logger.info(f"=== Scene {i+1}/5: {scene['title']} ===")

        try:
            # Use this scene's unique first-frame image
            first_frame = scene_first_frames[i]
            task_id, model_used = submit_video_task(
                scene["video_prompt"],
                image_url=first_frame if os.path.exists(first_frame) else char_ref_url,
                duration=VIDEO_DURATION,
            )
            result = poll_video_task(task_id)
            vid_url = extract_video_url(result)
            download_file(vid_url, video_path)
            video_paths.append(video_path)
            logger.info(f"Scene {i+1} done (model={model_used})")

        except Exception as e:
            logger.error(f"Scene {i+1} failed: {e}")
            raise

    # ---- Step 4: Concatenate ----
    logger.info("=== Step 4: Concatenating all scenes ===")
    final_path = str(WORKING_DIR / "baby_physics_50s_v2.mp4")
    concatenate_videos(video_paths, final_path)

    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    print(f"\n{'='*50}")
    print(f"VIDEO COMPLETE: {final_path}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Scenes: {len(video_paths)} x {VIDEO_DURATION}s")
    print(f"{'='*50}")
    return final_path


if __name__ == "__main__":
    result = main()
    if result:
        print(f"OUTPUT: {result}")
    else:
        print("FAILED")
        sys.exit(1)
