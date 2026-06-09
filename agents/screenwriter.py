"""
Screenwriter Agent - LLM-powered story, script, and character description generation.

Uses Doubao Ark API for chat completions.
"""
import json
import logging
import os
import requests
from typing import List, Optional

logger = logging.getLogger(__name__)


class Screenwriter:
    """LLM agent that develops stories, writes scripts, and generates character references."""

    def __init__(self, api_key: str, model: str = "doubao-1-5-pro-32k", base_url: str = "https://ark.cn-beijing.volces.com/api/v3"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.chat_url = f"{self.base_url}/chat/completions"

    def _chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        """Send a chat completion request to Doubao."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature
        }

        resp = requests.post(self.chat_url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.7):
        """Chat with JSON output parsing."""
        text = self._chat(system_prompt, user_prompt, temperature)
        # Try to extract JSON from the response
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON block in markdown
            import re
            json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            raise ValueError(f"Failed to parse JSON from LLM response: {text[:500]}")

    def develop_story(self, idea: str, user_requirement: str, style: str) -> dict:
        """Expand an idea into a full story with characters and narrative structure."""
        system_prompt = """你是一位专业的影视编剧和导演。你擅长将简单的想法扩展为完整的影视故事，包含角色设定、场景描述和叙事结构。
你的输出必须是严格的JSON格式。"""
        user_prompt = f"""请将以下想法扩展为一个完整的影视故事：

想法：{idea}
用户要求：{user_requirement}
风格：{style}

请以JSON格式输出，包含以下字段：
- "title": 故事标题
- "characters": 角色列表，每个角色包含 "name", "appearance", "personality"
- "narrative": 完整的叙事描述（200-400字）
- "scenes_count": 建议的场景数量（3-6个）

只输出JSON，不要其他文字。"""

        return self._chat_json(system_prompt, user_prompt)

    def write_script(self, story: dict, user_requirement: str, style: str) -> List[str]:
        """Divide the story into scene-level visual prompts for video generation."""
        system_prompt = """你是一位专业的影视分镜师。你需要将故事分解为多个场景，每个场景用英文描述，用于AI视频生成。
每个场景描述应该：
1. 用英文书写
2. 描述清楚视觉画面、动作、镜头运动
3. 长度80-150个英文单词
4. 适合作为视频生成的prompt
5. 场景之间要有连贯性"""
        user_prompt = f"""请将以下故事分解为场景视觉描述：

故事标题：{story.get('title', 'Untitled')}
角色：{json.dumps(story.get('characters', []), ensure_ascii=False)}
叙事：{story.get('narrative', '')}
用户要求：{user_requirement}
风格：{style}

请输出一个JSON数组，每个元素是一个场景的英文视觉描述字符串。
场景数量：{story.get('scenes_count', 4)}

只输出JSON数组，不要其他文字。"""

        return self._chat_json(system_prompt, user_prompt)

    def extract_character_description(self, story: dict, style: str) -> str:
        """Generate a character reference image prompt from the story."""
        system_prompt = """你是一位AI图像生成专家。你需要根据故事中的角色描述，生成一个用于AI生图的英文prompt。
这个prompt应该描述主角的外貌、服装、姿态，适合生成一致的角色参考图。"""
        user_prompt = f"""请为以下故事的主角生成一个角色参考图的英文prompt：

故事标题：{story.get('title', 'Untitled')}
角色：{json.dumps(story.get('characters', []), ensure_ascii=False)}
风格：{style}

要求：
1. 用英文
2. 描述主角的全身外观
3. 包含服装、发型、体态等细节
4. 适合作为视频生成的角色一致性参考
5. 长度50-100个英文单词

只输出prompt文本，不要其他文字。"""

        return self._chat(system_prompt, user_prompt, temperature=0.5)

    def generate_end_frame_prompts(self, scenes: List[str], style: str) -> List[str]:
        """Generate end-of-scene frame prompts for keyframes chaining mode."""
        system_prompt = """你是一位视频分镜专家。你需要为每个场景生成一个"结尾帧"的描述。
这个结尾帧将作为下一个场景的开头帧，用于视频的连贯衔接。
请用英文描述每个场景最后一帧的静态画面。"""
        user_prompt = f"""请为以下每个场景生成结尾帧描述：

场景列表：
{json.dumps(scenes, indent=2, ensure_ascii=False)}
风格：{style}

输出一个JSON数组，每个元素是对应场景结尾帧的英文描述（30-60个单词）。
只输出JSON数组。"""

        return self._chat_json(system_prompt, user_prompt)
