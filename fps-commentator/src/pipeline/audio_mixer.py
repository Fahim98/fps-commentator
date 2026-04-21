"""
Audio Mixer - Merges commentary audio with original game video using FFmpeg.
"""

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

from .tts_engine import AudioSegment

logger = logging.getLogger(__name__)


class AudioMixer:
    """
    Mixes AI commentary audio segments with the original game video.

    Strategy:
    1. Extract original audio from video
    2. Build a complex FFmpeg filter that:
       - Places each commentary clip at the right timestamp
       - Ducks (lowers) game audio when commentary is playing
    3. Merge everything back into the output video
    """

    def __init__(self, duck_audio: bool = True, duck_volume: float = 0.3):
        self._check_ffmpeg()
        self.duck_audio = duck_audio
        self.duck_volume = duck_volume

    def _check_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            raise RuntimeError(
                "FFmpeg not found. Install it with: brew install ffmpeg (macOS) "
                "or apt-get install ffmpeg (Linux)"
            )

    async def mix(
        self,
        video_path: Path,
        commentary_segments: list[AudioSegment],
        output_path: Path,
    ) -> None:
        """
        Mix commentary audio with video and save to output_path.

        Args:
            video_path: Original video file.
            commentary_segments: List of AudioSegments with timing and audio paths.
            output_path: Where to save the final video.
        """
        if not commentary_segments:
            logger.warning("No commentary segments — copying video as-is.")
            shutil.copy2(video_path, output_path)
            return

        if self.duck_audio:
            await self._mix_with_ducking(video_path, commentary_segments, output_path)
        else:
            await self._mix_simple(video_path, commentary_segments, output_path)

    async def _mix_with_ducking(
        self,
        video_path: Path,
        segments: list[AudioSegment],
        output_path: Path,
    ) -> None:
        """
        Advanced mix: game audio ducks under commentary using FFmpeg sidechaining.
        """
        filter_complex = self._build_duck_filter(segments)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            *self._build_audio_inputs(segments),
            "-filter_complex", filter_complex,
            "-map", "0:v",             # Original video stream
            "-map", "[final_mix]",     # Mixed audio
            "-c:v", "copy",            # No video re-encoding
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path),
        ]

        await self._run_ffmpeg(cmd)

    async def _mix_simple(
        self,
        video_path: Path,
        segments: list[AudioSegment],
        output_path: Path,
    ) -> None:
        """
        Simple mix: commentary audio overlaid at full volume on top of game audio.
        """
        filter_complex = self._build_simple_filter(segments)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            *self._build_audio_inputs(segments),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[final_mix]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path),
        ]

        await self._run_ffmpeg(cmd)

    def _build_audio_inputs(self, segments: list[AudioSegment]) -> list[str]:
        """Build FFmpeg -i flags for each commentary audio file."""
        inputs = []
        for seg in segments:
            inputs.extend(["-i", str(seg.audio_path)])
        return inputs

    def _build_simple_filter(self, segments: list[AudioSegment]) -> str:
        """
        FFmpeg filter that delays each commentary clip and mixes with game audio.

        [0:a] = original game audio (input 0)
        [1:a] = first commentary clip (input 1)
        [2:a] = second commentary clip (input 2)
        etc.
        """
        parts = ["[0:a]aformat=sample_rates=44100:channel_layouts=stereo[game]"]

        delayed = []
        for idx, seg in enumerate(segments):
            delay_ms = int(seg.cue.speak_at_seconds * 1000)
            label = f"[c{idx}]"
            parts.append(f"[{idx + 1}:a]adelay={delay_ms}|{delay_ms}{label}")
            delayed.append(label)

        all_inputs = "[game]" + "".join(delayed)
        n_inputs = len(delayed) + 1
        parts.append(f"{all_inputs}amix=inputs={n_inputs}:normalize=0[final_mix]")

        return "; ".join(parts)

    def _build_duck_filter(self, segments: list[AudioSegment]) -> str:
        """
        FFmpeg filter with audio ducking: game audio volume drops when commentary plays.

        Uses volume automation via the 'volume' filter with enable expressions.
        """
        # Build enable time ranges for when commentary is active
        duck_ranges = []
        for seg in segments:
            start = seg.cue.speak_at_seconds
            end = start + seg.duration_seconds + 0.3  # Small tail
            duck_ranges.append(f"between(t,{start:.2f},{end:.2f})")

        enable_expr = "+".join(duck_ranges) if duck_ranges else "0"

        # Game audio with volume automation
        duck_filter = (
            f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"volume=enable='{enable_expr}':volume={self.duck_volume}[game_ducked]"
        )
        parts = [duck_filter]

        # Delay and label each commentary clip
        delayed = []
        for idx, seg in enumerate(segments):
            delay_ms = int(seg.cue.speak_at_seconds * 1000)
            label = f"[c{idx}]"
            parts.append(f"[{idx + 1}:a]adelay={delay_ms}|{delay_ms}{label}")
            delayed.append(label)

        # Mix everything
        all_inputs = "[game_ducked]" + "".join(delayed)
        n_inputs = len(delayed) + 1
        parts.append(f"{all_inputs}amix=inputs={n_inputs}:normalize=0[final_mix]")

        return "; ".join(parts)

    async def _run_ffmpeg(self, cmd: list[str]) -> None:
        """Run an FFmpeg command asynchronously."""
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed (exit {process.returncode}):\n{stderr.decode()[-2000:]}"
            )

        logger.debug("FFmpeg completed successfully.")
