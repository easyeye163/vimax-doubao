# ViMax-Doubao: Agentic Video Generation powered by Doubao Seedance

<p align="center">
  <b>Idea → Story → Script → Images → Video</b><br>
  <i>Powered by ByteDance Doubao Seedance (豆包即梦)</i>
</p>

## Overview

ViMax-Doubao is a lightweight adaptation of [ViMax](https://github.com/HKUDS/ViMax) that replaces Google Veo/Gemini with **ByteDance Doubao Seedance API** for agentic video generation.

The pipeline is fully autonomous: you provide an idea, and the system generates a complete video through a multi-step agentic workflow powered by LLM + Image Generation + Video Generation.

## Architecture

```
┌──────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐    ┌────────────┐
│   Idea    │───▶│ Screenwriter │───▶│ Image Generator │───▶│ Video Generator  │───▶│ Final Video│
│  (用户想法) │    │  (剧本/分镜)  │    │   (参考图生成)    │    │ (豆包 Seedance)  │    │  (合并输出) │
└──────────┘    └──────────────┘    └─────────────────┘    └──────────────────┘    └────────────┘
```

### Pipeline Flow

1. **Story Development** — LLM expands your idea into a structured story with characters
2. **Script Writing** — LLM divides the story into scene-level visual prompts
3. **Character Reference** — Generate a consistent character reference image
4. **Video Generation** — Each scene becomes a video clip via Doubao Seedance
5. **Concatenation** — All clips are merged into a final video

## Quick Start

### 1. Get API Key

Register at [火山引擎方舟平台](https://console.volcengine.com/ark) and get your API Key (Endpoint ID).

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

```bash
export DOUBAO_API_KEY="your-doubao-ark-api-key"
```

Or edit `configs/idea2video.yaml`.

### 4. Run

```bash
python main_idea2video.py
```

## Doubao Seedance API

### Create Image-to-Video Task

```bash
curl -X POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {DOUBAO_API_KEY}" \
  -d '{
    "model": "doubao-seedance-1-5-pro-251215",
    "content": [
        {
            "type": "text",
            "text": "Your prompt here --duration 5 --camerafixed false --watermark true"
        },
        {
            "type": "image_url",
            "image_url": {
                "url": "https://example.com/your-image.png"
            }
        }
    ]
}'
```

### Query Task Status

```bash
curl -X GET https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id} \
  -H "Authorization: Bearer {DOUBAO_API_KEY}"
```

### Prompt Parameters

| Parameter | Description | Values |
|-----------|-------------|--------|
| `--duration` | Video duration in seconds | 5 / 10 |
| `--camerafixed` | Fix camera perspective | true / false |
| `--watermark` | Add watermark | true / false |
| `--seed` | Random seed for reproducibility | Integer |

### Video Duration Presets

| Duration | Model | Notes |
|----------|-------|-------|
| 5s | doubao-seedance-1-5-pro-251215 | Default, stable |
| 10s | doubao-seedance-1-5-pro-251215 | Supported with --duration 10 |

## Project Structure

```
vimax-doubao/
├── configs/
│   └── idea2video.yaml          # Pipeline configuration
├── agents/
│   └── screenwriter.py          # LLM-powered story & script agent
├── interfaces/
│   ├── shot_description.py      # Shot description data model
│   └── video_output.py          # Image/Video output containers
├── pipelines/
│   └── idea2video_pipeline.py   # Core orchestration pipeline
├── tools/
│   ├── image_generator_doubao_api.py  # Doubao image generation
│   ├── video_generator_doubao_api.py  # Doubao Seedance video generation
│   ├── protocols.py             # Type contracts
│   └── render_backend.py        # Generator factory
├── utils/
│   ├── image.py                  # Image download helpers
│   └── video.py                  # Video download helpers
├── main_idea2video.py           # Entry point
├── run_full_pipeline.py         # Full standalone pipeline script
└── requirements.txt
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DOUBAO_API_KEY` | Doubao Ark API Key | Yes |

### Video Settings (in main_idea2video.py)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `idea` | Your video idea | (see code) |
| `user_requirement` | Style & technical requirements | (see code) |
| `style` | Visual style description | (see code) |
| `reference_image` | Path to reference image | None |
| `chaining_mode` | Scene chaining: "none" / "ti2vid" | "ti2vid" |
| `video_width` | Output video width | 768 |
| `video_height` | Output video height | 1152 |

## Differences from vimax-agnes

| Feature | vimax-agnes | vimax-doubao |
|---------|-------------|--------------|
| LLM | Agnes 2.0 Flash | Doubao 1.5 Pro 32K |
| Image Gen | Agnes Image 2.1 Flash | Doubao Seedream 3.0 |
| Video Gen | Agnes Video v2.0 | Doubao Seedance 1.5 Pro |
| Video API | REST + polling | REST + polling |
| Max Duration | 10s | 10s |
| Chaining | ti2vid / keyframes | ti2vid |
| API Base | apihub.agnes-ai.com | ark.cn-beijing.volces.com |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [ViMax](https://github.com/HKUDS/ViMax) - Original agentic video generation framework
- [Doubao Seedance](https://console.volcengine.com/ark) - ByteDance's video generation API
