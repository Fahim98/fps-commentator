"""
Commentary Writer - Uses Claude to generate contextual, timed commentary lines.
"""

import logging
from dataclasses import dataclass

import anthropic

from .video_analyzer import VideoAnalysis, GameEvent
from ..utils.config import get_settings

logger = logging.getLogger(__name__)

# Persona system prompts
PERSONAS = {
    "hype_caster": """You are an ELECTRIFYING esports hype caster like a Valorant Champions announcer.
You live for insane plays. Your commentary is loud, passionate, and full of energy.
Use phrases like "WHAT A PLAY!", "ABSOLUTELY MENTAL!", "NO WAY HE HITS THAT!"
Keep each line punchy — max 15 words. React to EXACTLY what happens in the clip.""",

    "analyst": """You are a calm, insightful tactical analyst commentating FPS gameplay.
Focus on decision-making, positioning, and game sense. Sound like a seasoned coach breaking down film.
Use phrases like "Notice how he pre-aims...", "Smart use of cover here", "The read on that angle was perfect."
Keep lines under 20 words. Be specific and educational.""",

    "funny": """You are a comedic gaming commentator — think Internet Comment Etiquette meets a Twitch streamer.
You roast bad plays, hype good ones, and add absurd observations.
Use humor, self-awareness, and internet humor. Example: "He said 'skill issue' with a HEADSHOT."
Keep lines under 15 words. Be genuinely funny, not try-hard.""",

    "chill": """You are a laid-back, chill gaming commentator. Like a friend watching over your shoulder.
Conversational, relaxed, authentic. Not too loud, not too quiet.
Example: "ooh nice peek", "that was actually clean", "yeah he's not surviving that"
Short, natural reactions. Max 12 words. Sound real, not scripted.""",
}

COMMENTARY_PROMPT = """
Game: {game_title}
Clip Summary: {summary}

Events to commentate on (in chronological order):
{events_text}

Generate exactly ONE commentary line per event listed above.
Each line should:
- React to that SPECIFIC event (not generic)
- Be timed to fire right when the action happens
- Vary in energy — not every line can be at max intensity
- Feel like natural spoken commentary (contractions, casual phrasing)

Respond ONLY with a JSON array, one object per event:
[
  {{
    "timestamp_seconds": <match the event timestamp exactly>,
    "text": "<commentary line>",
    "pause_before_seconds": <0.0 to 1.5, how long to wait after event before speaking>
  }}
]
"""


@dataclass
class CommentaryCue:
    """A single timed commentary line to be spoken."""
    timestamp_seconds: float      # When the trigger event happens
    speak_at_seconds: float       # When to actually start speaking (after pause)
    text: str                     # The commentary text
    pause_before_seconds: float   # How long to wait before speaking


class CommentaryWriter:
    """Generates contextual commentary using Claude."""

    def __init__(self, persona: str = "hype_caster"):
        if persona not in PERSONAS:
            raise ValueError(f"Unknown persona '{persona}'. Choose from: {list(PERSONAS.keys())}")

        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.persona = persona
        self.system_prompt = PERSONAS[persona]

    async def generate(self, analysis: VideoAnalysis, density: float = 0.6) -> list[CommentaryCue]:
        """
        Generate timed commentary cues for commentable events.

        Args:
            analysis: The video analysis with detected events.
            density: 0.0 = only highlight the best moments, 1.0 = comment on everything.

        Returns:
            List of CommentaryCue objects sorted by timestamp.
        """
        events = self._filter_by_density(analysis.highlight_events, density)

        if not events:
            logger.warning("No commentable events found in clip.")
            return []

        events_text = self._format_events(events)
        prompt = COMMENTARY_PROMPT.format(
            game_title=analysis.game_title,
            summary=analysis.overall_summary,
            events_text=events_text,
        )

        logger.debug(f"Sending {len(events)} events to Claude for commentary...")
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_response(message.content[0].text)

    def _filter_by_density(self, events: list[GameEvent], density: float) -> list[GameEvent]:
        """Filter events based on commentary density. Always keep high-intensity events."""
        if density >= 1.0:
            return events

        # Sort by intensity, keep top percentage
        sorted_events = sorted(events, key=lambda e: e.intensity, reverse=True)
        keep_count = max(1, int(len(sorted_events) * density))

        # Always keep intensity >= 7 events regardless of density
        must_keep = [e for e in events if e.intensity >= 7]
        optional = [e for e in sorted_events if e.intensity < 7][:keep_count]

        combined = list({e.timestamp_seconds: e for e in must_keep + optional}.values())
        return sorted(combined, key=lambda e: e.timestamp_seconds)

    def _format_events(self, events: list[GameEvent]) -> str:
        lines = []
        for e in events:
            lines.append(
                f"- [{e.timestamp_seconds:.1f}s] {e.event_type.upper()} (intensity {e.intensity}/10): {e.description}"
            )
        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> list[CommentaryCue]:
        import json

        # Strip markdown code blocks if present
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Claude returned invalid JSON: {e}\nResponse: {text[:500]}")

        cues = []
        for item in data:
            timestamp = float(item["timestamp_seconds"])
            pause = float(item.get("pause_before_seconds", 0.3))
            cues.append(CommentaryCue(
                timestamp_seconds=timestamp,
                speak_at_seconds=timestamp + pause,
                text=item["text"],
                pause_before_seconds=pause,
            ))

        return sorted(cues, key=lambda c: c.speak_at_seconds)
