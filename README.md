# 🎮 FPS Commentator

> Add AI voiceover commentary to your FPS game clips — automatically.

FPS Commentator analyzes your gameplay video, detects key events (kills, clutches, multi-kills), generates contextual commentary in a chosen persona, and mixes it into the final video with proper audio ducking.


---

## How It Works

```
Video Clip
    │
    ▼
[Gemini 2.0 Flash]        ← Watches the clip, detects events + timestamps
    │
    ▼
[Claude Sonnet]           ← Writes commentary lines in your chosen persona
    │
    ▼
[ElevenLabs TTS]          ← Synthesizes natural-sounding voice (in parallel)
    │
    ▼
[FFmpeg]                  ← Mixes audio, ducks game sound, renders output
    │
    ▼
Final Video with Voiceover
```

---

## Features

- 🎯 **Event detection** — kills, headshots, multi-kills, clutches, deaths, abilities
- 🎙️ **4 commentator personas** — Hype Caster, Analyst, Funny, Chill
- 🔊 **Audio ducking** — game audio automatically lowers when commentary plays
- ⚡ **Parallel TTS** — all commentary lines synthesized concurrently
- 🎛️ **Commentary density** — control how often the AI speaks (0% to 100%)
- 🎮 **Game-agnostic** — works with any FPS: Valorant, CS2, CoD, Apex, etc.

---

## Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/download.html) (`brew install ffmpeg` or `apt install ffmpeg`)
- API keys for:
  - [Anthropic](https://console.anthropic.com/) (Claude)
  - [Google AI Studio](https://aistudio.google.com/) (Gemini)
  - [ElevenLabs](https://elevenlabs.io/) (TTS)

---

## Installation

```bash
git clone https://github.com/Fahim98/fps-commentator
cd fps-commentator

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .
```

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

```env
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
ELEVENLABS_API_KEY=...
```

---

## Usage

### CLI

```bash
# Basic — hype caster persona at default density
fps-commentator clip.mp4

# Analyst persona, sparse commentary
fps-commentator clip.mp4 --persona analyst --density 0.3

# Funny persona, custom output path
fps-commentator clip.mp4 --persona funny -o funny_clip.mp4

# Don't duck game audio
fps-commentator clip.mp4 --no-duck

# All options
fps-commentator --help
```

### Python API

```python
import asyncio
from src.pipeline.commentator import FPSCommentator, CommentaryConfig

config = CommentaryConfig(
    persona="hype_caster",       # hype_caster | analyst | funny | chill
    commentary_density=0.7,      # 0.0 sparse → 1.0 constant
    duck_game_audio=True,
    duck_volume=0.25,            # Game audio volume during commentary
)

commentator = FPSCommentator(config=config)
result = asyncio.run(commentator.process("clip.mp4"))

print(f"Output:   {result.output_path}")
print(f"Events:   {result.events_detected}")
print(f"Lines:    {result.commentary_lines}")
```

---

## Personas

| Persona | Style | Example |
|---|---|---|
| `hype_caster` | Electrifying esports energy | *"ABSOLUTELY INSANE! He one-taps through smoke!"* |
| `analyst` | Tactical, educational | *"Smart pre-aim on that corner — he knew they'd push."* |
| `funny` | Comedic, self-aware | *"Bro said 'skill issue' with a no-scope."* |
| `chill` | Laid-back, conversational | *"ooh that was actually clean ngl"* |

---

## Project Structure

```
fps-commentator/
├── src/
│   ├── pipeline/
│   │   ├── commentator.py        # Main orchestrator
│   │   ├── video_analyzer.py     # Gemini video understanding
│   │   ├── commentary_writer.py  # Claude commentary generation
│   │   ├── tts_engine.py         # ElevenLabs TTS synthesis
│   │   └── audio_mixer.py        # FFmpeg audio mixing
│   └── utils/
│       └── config.py             # Settings / env vars
├── tests/
│   └── test_commentary_writer.py
├── cli.py                        # CLI entry point
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Costs (Approximate)

For a 60-second clip with ~10 commentary lines:

| Service | Usage | Est. Cost |
|---|---|---|
| Gemini 2.0 Flash | 1 video analysis | ~$0.01 |
| Claude Sonnet | ~500 tokens | ~$0.002 |
| ElevenLabs Turbo | ~150 words | ~$0.02 |
| **Total** | | **~$0.03/clip** |

---

## Roadmap

- [ ] Batch processing (folder of clips)
- [ ] Web UI for upload + preview
- [ ] Custom voice cloning support
- [ ] Support for reaction-style commentary (post-clip)
- [ ] Twitch/YouTube direct upload integration
- [ ] Subtitle/caption generation alongside audio

---

## Contributing

PRs welcome! Please open an issue first for major changes.

```bash
pip install -e ".[dev]"
pytest
```

---

## License

MIT
