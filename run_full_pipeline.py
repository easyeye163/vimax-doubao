#!/usr/bin/env python3
"""
run_full_pipeline.py - Standalone full pipeline for Doubao Seedance.

A self-contained script that runs the complete idea-to-video pipeline
without requiring YAML config. Just set your API key and run.
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
CHAT_MODEL = "doubao-1-5-pro-32k"
IMAGE_MODEL = "doubao-seedream-3-0-t2i-250415"
VIDEO_MODEL = "doubao-seedance-1-5-pro-251215"
VIDEO_DURATION = 5
WORKING_DIR = Path(".working_dir/demo")

IDEA = "一个女孩在海边看日出，随着音乐起舞，镜头从远景慢慢推进到特写"
USER_REQUIREMENT = "3个场景，竖屏短视频，电影质感"
STYLE = "cinematic music video, golden hour lighting"
# ========================================


def chat_completion(prompt: str, system: str = "You are a helpful assistant.") -> str:
    """Call Doubao chat API."""
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def generate_image(prompt: str) -> str:
    """Generate an image and return the URL."""
    resp = requests.post(
        f"{BASE_URL}/images/generations",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": IMAGE_MODEL, "prompt": prompt, "size": "1024x1024", "n": 1},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["url"]


def submit_video_task(prompt: str, image_url: str = None) -> str:
    """Submit a video generation task."""
    content = [{"type": "text", "text": f"{prompt} --duration {VIDEO_DURATION} --camerafixed false --watermark true"}]
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


def poll_video_task(task_id: str, timeout: int = 900) -> dict:
    """Poll video task until complete."""
    url = f"{BASE_URL}/contents/generations/tasks/{task_id}"
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "unknown")
        logger.info(f"  Task {task_id}: status={status}")
        if status in ("succeeded", "completed"):
            return data
        if status == "failed":
            raise RuntimeError(f"Task failed: {json.dumps(data, ensure_ascii=False)[:300]}")
        time.sleep(15)
    raise TimeoutError(f"Task {task_id} timed out")


def extract_video_url(task_result: dict) -> str:
    """Extract video URL from task result."""
    for item in task_result.get("content", []):
        if item.get("type") in ("video_url", "video"):
            return item.get("video_url", {}).get("url", "") or item.get("url", "")
    if "output" in task_result:
        return task_result["output"].get("video_url", "")
    raise ValueError(f"No video URL in result: {json.dumps(task_result, ensure_ascii=False)[:300]}")


def download_file(url: str, path: str):
    """Download a file from URL."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)
    logger.info(f"Downloaded: {path}")


def extract_last_frame(video_path: str, output_path: str) -> bool:
    """Extract last frame from video."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-sseof", "-0.1", "-i", video_path, "-frames:v", "1", "-q:v", "2", output_path],
            capture_output=True, timeout=60, check=True
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to extract last frame: {e}")
        return False


def concatenate_videos(video_paths: list, output_path: str):
    """Concatenate videos with ffmpeg."""
    concat_file = str(WORKING_DIR / "concat.txt")
    with open(concat_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path],
        capture_output=True, timeout=120, check=True
    )
    logger.info(f"Final video: {output_path}")


def main():
    WORKING_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Develop story
    logger.info("=== Step 1: Developing story ===")
    story_prompt = f"""将以下想法扩展为故事，输出JSON：
- "title": 标题
- "narrative": 叙事（200字）
- "scenes_count": 场景数(3-5)

想法：{IDEA}
要求：{USER_REQUIREMENT}
风格：{STYLE}

只输出JSON。"""
    story_text = chat_completion(story_prompt, system="你是专业编剧，输出严格JSON。")
    import re
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', story_text, re.DOTALL)
    story = json.loads(json_match.group(1) if json_match else story_text)
    with open(WORKING_DIR / "story.json", "w") as f:
        json.dump(story, f, ensure_ascii=False, indent=2)
    logger.info(f"Story: {story.get('title', 'N/A')}")

    # Step 2: Write script
    logger.info("=== Step 2: Writing script ===")
    script_prompt = f"""将故事分解为{story.get('scenes_count', 3)}个场景的英文视觉prompt（每个80-150词），输出JSON数组。
故事：{story.get('narrative', '')}
风格：{STYLE}
只输出JSON数组。"""
    script_text = chat_completion(script_prompt, system="你是分镜师，输出严格JSON数组。")
    scenes = json.loads(re.search(r'```(?:json)?\s*\n(.*?)\n```', script_text, re.DOTALL).group(1) if re.search(r'```(?:json)?\s*\n(.*?)\n```', script_text, re.DOTALL) else script_text)
    with open(WORKING_DIR / "script.json", "w") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)
    logger.info(f"Script: {len(scenes)} scenes")

    # Step 3: Generate character reference
    logger.info("=== Step 3: Generating character reference ===")
    char_prompt = "A beautiful young woman in a flowing white dress, standing on a beach at sunrise, cinematic portrait, golden hour lighting, 8K quality"
    try:
        char_url = generate_image(char_prompt)
        char_path = str(WORKING_DIR / "character_reference.png")
        download_file(char_url, char_path)
    except Exception as e:
        logger.warning(f"Character reference failed: {e}")
        char_path = None

    # Step 4: Generate scene videos
    logger.info("=== Step 4: Generating scene videos ===")
    video_paths = []
    last_frame = char_path

    for i, scene in enumerate(scenes):
        logger.info(f"--- Scene {i+1}/{len(scenes)} ---")
        scene_dir = WORKING_DIR / f"scene_{i:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        video_path = str(scene_dir / "video.mp4")

        ref = last_frame if last_frame else None
        task_id = submit_video_task(scene, image_url=ref)
        result = poll_video_task(task_id)
        video_url = extract_video_url(result)
        download_file(video_url, video_path)
        video_paths.append(video_path)

        # Extract last frame for chaining
        frame_path = str(scene_dir / "last_frame.png")
        if extract_last_frame(video_path, frame_path):
            last_frame = frame_path

    # Step 5: Concatenate
    logger.info("=== Step 5: Concatenating ===")
    if len(video_paths) > 1:
        final_path = str(WORKING_DIR / "final_video.mp4")
        concatenate_videos(video_paths, final_path)
        print(f"\n=== DONE === Final video: {final_path}")
    else:
        print(f"\n=== DONE === Single video: {video_paths[0]}")


if __name__ == "__main__":
    main()
