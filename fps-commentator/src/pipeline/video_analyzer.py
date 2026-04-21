"""
Video Analyzer - Uses Google Gemini to understand FPS game events.
"""

import json
import logging
import base64
import mimetypes
from pathlib import Path
from dataclasses import dataclass, field

import google.generativeai as genai

from ..utils.config import get_settings

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """
You are an expert FPS game analyst. Watch this game clip carefully and identify every significant event.

For each event, provide:
1. timestamp_seconds - when it happens (float)
2. event_type - one of: kill, death, headshot, multi_kill, clutch_moment, reload, low_health, grenade_throw, ability_used, round_start, round_end, highlight
3. description - 1-2 sentence factual description of exactly what happens
4. intensity - 1 to 10 (10 = insane moment, 1 = routine play)
5. commentable - true/false (is this worth commenting on?)

Also provide:
- game_title: best guess at the game being played
- total_duration: video duration in seconds
- overall_summary: 2-3 sentence summary of the entire clip

Respond ONLY with valid JSON in this exact format:
{
  "game_title": "...",
  "total_duration": 0.0,
  "overall_summary": "...",
  "events": [
    {
      "timestamp_seconds": 0.0,
      "event_type": "kill",
      "description": "...",
      "intensity": 5,
      "commentable": true
    }
  ]
}
"""


@dataclass
class GameEvent:
    timestamp_seconds: float
    event_type: str
    description: str
    intensity: int
    commentable: bool


@dataclass
class VideoAnalysis:
    game_title: str
    duration: float
    overall_summary: str
    events: list[GameEvent] = field(default_factory=list)

    @property
    def highlight_events(self) -> list[GameEvent]:
        """Return only events worth commenting on, sorted by time."""
        return sorted(
            [e for e in self.events if e.commentable],
            key=lambda e: e.timestamp_seconds,
        )


class VideoAnalyzer:
    """Analyzes FPS clips using Google Gemini's video understanding."""

    def __init__(self):
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    async def analyze(self, video_path: Path) -> VideoAnalysis:
        """
        Send the video to Gemini and parse the structured event analysis.

        Args:
            video_path: Path to the video file.

        Returns:
            VideoAnalysis with all detected events.
        """
        logger.info(f"Uploading {video_path.name} to Gemini Files API...")
        video_file = await self._upload_video(video_path)

        logger.info("Sending analysis request to Gemini...")
        response = self.model.generate_content(
            [video_file, ANALYSIS_PROMPT],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        return self._parse_response(response.text)

    async def _upload_video(self, video_path: Path):
        """Upload video using Gemini Files API for videos > a few seconds."""
        mime_type, _ = mimetypes.guess_type(str(video_path))
        mime_type = mime_type or "video/mp4"

        # Use the Files API for larger videos
        video_file = genai.upload_file(
            path=str(video_path),
            mime_type=mime_type,
        )

        # Wait for processing
        import time
        while video_file.state.name == "PROCESSING":
            logger.debug("Waiting for Gemini to process video...")
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise RuntimeError(f"Gemini file processing failed: {video_file.state}")

        return video_file

    def _parse_response(self, response_text: str) -> VideoAnalysis:
        """Parse Gemini's JSON response into a VideoAnalysis object."""
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Gemini returned invalid JSON: {e}\nResponse: {response_text[:500]}")

        events = [
            GameEvent(
                timestamp_seconds=float(e["timestamp_seconds"]),
                event_type=e["event_type"],
                description=e["description"],
                intensity=int(e.get("intensity", 5)),
                commentable=bool(e.get("commentable", True)),
            )
            for e in data.get("events", [])
        ]

        return VideoAnalysis(
            game_title=data.get("game_title", "Unknown Game"),
            duration=float(data.get("total_duration", 0)),
            overall_summary=data.get("overall_summary", ""),
            events=events,
        )
