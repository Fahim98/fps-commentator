"""
TTS Engine - Converts commentary text to audio using ElevenLabs.
"""

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

from .commentary_writer import CommentaryCue
from ..utils.config import get_settings

logger = logging.getLogger(__name__)

# ElevenLabs voice presets per persona
PERSONA_VOICES = {
    "hype_caster": {
        "voice_id": "pNInz6obpgDQGcFmaJgB",   # Adam - energetic male
        "stability": 0.35,
        "similarity_boost": 0.85,
        "style": 0.75,                          # High expressiveness
        "use_speaker_boost": True,
    },
    "analyst": {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",   # Rachel - clear, calm
        "stability": 0.75,
        "similarity_boost": 0.80,
        "style": 0.20,
        "use_speaker_boost": False,
    },
    "funny": {
        "voice_id": "AZnzlk1XvdvUeBnXmlld",   # Domi - playful
        "stability": 0.45,
        "similarity_boost": 0.75,
        "style": 0.65,
        "use_speaker_boost": True,
    },
    "chill": {
        "voice_id": "ErXwobaYiN019PkySvjV",   # Antoni - relaxed
        "stability": 0.80,
        "similarity_boost": 0.70,
        "style": 0.10,
        "use_speaker_boost": False,
    },
}


@dataclass
class AudioSegment:
    """A synthesized audio segment with timing metadata."""
    cue: CommentaryCue
    audio_path: Path
    duration_seconds: float


class TTSEngine:
    """Text-to-speech using ElevenLabs API."""

    def __init__(self, voice_id: str = "default", persona: str = "hype_caster"):
        settings = get_settings()
        self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)

        voice_config = PERSONA_VOICES.get(persona, PERSONA_VOICES["hype_caster"])
        self.voice_id = voice_id if voice_id != "default" else voice_config["voice_id"]
        self.voice_settings = VoiceSettings(
            stability=voice_config["stability"],
            similarity_boost=voice_config["similarity_boost"],
            style=voice_config.get("style", 0.5),
            use_speaker_boost=voice_config.get("use_speaker_boost", True),
        )
        self._temp_dir = Path(tempfile.mkdtemp(prefix="fps_commentator_"))

    async def synthesize_all(self, cues: list[CommentaryCue]) -> list[AudioSegment]:
        """
        Synthesize all commentary cues concurrently.

        Args:
            cues: List of CommentaryCue objects to synthesize.

        Returns:
            List of AudioSegment objects with paths to audio files.
        """
        tasks = [self._synthesize_one(cue, idx) for idx, cue in enumerate(cues)]
        segments = await asyncio.gather(*tasks)
        return [s for s in segments if s is not None]

    async def _synthesize_one(self, cue: CommentaryCue, idx: int) -> AudioSegment | None:
        """Synthesize a single commentary line."""
        output_path = self._temp_dir / f"commentary_{idx:03d}.mp3"

        try:
            logger.debug(f"TTS [{idx}]: '{cue.text[:50]}...'")

            # Run in thread pool since ElevenLabs client is synchronous
            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(None, self._call_elevenlabs, cue.text)

            output_path.write_bytes(audio_bytes)
            duration = self._get_audio_duration(output_path)

            return AudioSegment(
                cue=cue,
                audio_path=output_path,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error(f"TTS failed for cue {idx}: {e}")
            return None

    def _call_elevenlabs(self, text: str) -> bytes:
        """Synchronous ElevenLabs API call."""
        audio_generator = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id="eleven_turbo_v2_5",   # Fastest, good quality
            voice_settings=self.voice_settings,
            output_format="mp3_44100_128",
        )
        return b"".join(audio_generator)

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get duration of an MP3 file using mutagen."""
        try:
            from mutagen.mp3 import MP3
            audio = MP3(str(audio_path))
            return audio.info.length
        except Exception:
            # Fallback: estimate from file size (rough)
            size_kb = audio_path.stat().st_size / 1024
            return size_kb / 16  # ~16KB/s at 128kbps

    def cleanup(self):
        """Remove temporary audio files."""
        import shutil
        shutil.rmtree(self._temp_dir, ignore_errors=True)
