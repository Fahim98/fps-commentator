"""
FPS Commentator - Main Pipeline Orchestrator
Analyzes FPS game clips and generates AI voiceover commentary.
"""

import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass

from .video_analyzer import VideoAnalyzer
from .commentary_writer import CommentaryWriter
from .tts_engine import TTSEngine
from .audio_mixer import AudioMixer

logger = logging.getLogger(__name__)


@dataclass
class CommentaryConfig:
    """Configuration for the commentary pipeline."""
    persona: str = "hype_caster"          # hype_caster | analyst | funny | chill
    commentary_density: float = 0.6       # 0.0 = sparse, 1.0 = constant
    duck_game_audio: bool = True          # Lower game audio when speaking
    duck_volume: float = 0.3             # Game audio volume during voiceover (0.0-1.0)
    tts_voice_id: str = "default"        # ElevenLabs voice ID or "default"
    output_suffix: str = "_commentary"   # Appended to output filename


@dataclass
class PipelineResult:
    """Result from the commentary pipeline."""
    output_path: Path
    events_detected: int
    commentary_lines: int
    duration_seconds: float
    success: bool
    error: str | None = None


class FPSCommentator:
    """
    Full pipeline for adding AI voiceover commentary to FPS game clips.

    Usage:
        commentator = FPSCommentator(config=CommentaryConfig(persona="hype_caster"))
        result = await commentator.process("clip.mp4")
        print(f"Output: {result.output_path}")
    """

    def __init__(self, config: CommentaryConfig | None = None):
        self.config = config or CommentaryConfig()
        self.analyzer = VideoAnalyzer()
        self.writer = CommentaryWriter(persona=self.config.persona)
        self.tts = TTSEngine(voice_id=self.config.tts_voice_id)
        self.mixer = AudioMixer(
            duck_audio=self.config.duck_game_audio,
            duck_volume=self.config.duck_volume,
        )

    async def process(self, video_path: str | Path, output_path: str | Path | None = None) -> PipelineResult:
        """
        Process a video clip end-to-end.

        Args:
            video_path: Path to the input FPS game clip.
            output_path: Optional path for the output video. Defaults to
                         <input_name>_commentary.<ext> in the same directory.

        Returns:
            PipelineResult with details of the processing.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return PipelineResult(
                output_path=video_path,
                events_detected=0,
                commentary_lines=0,
                duration_seconds=0,
                success=False,
                error=f"File not found: {video_path}",
            )

        if output_path is None:
            output_path = video_path.with_name(
                f"{video_path.stem}{self.config.output_suffix}{video_path.suffix}"
            )
        output_path = Path(output_path)

        try:
            logger.info(f"[1/4] Analyzing video: {video_path.name}")
            analysis = await self.analyzer.analyze(video_path)
            logger.info(f"      Detected {len(analysis.events)} game events over {analysis.duration:.1f}s")

            logger.info("[2/4] Generating commentary...")
            commentary_cues = await self.writer.generate(
                analysis=analysis,
                density=self.config.commentary_density,
            )
            logger.info(f"      Generated {len(commentary_cues)} commentary lines")

            logger.info("[3/4] Synthesizing voiceover audio...")
            audio_segments = await self.tts.synthesize_all(commentary_cues)

            logger.info("[4/4] Mixing audio and rendering output...")
            await self.mixer.mix(
                video_path=video_path,
                commentary_segments=audio_segments,
                output_path=output_path,
            )

            logger.info(f"Done! Output saved to: {output_path}")
            return PipelineResult(
                output_path=output_path,
                events_detected=len(analysis.events),
                commentary_lines=len(commentary_cues),
                duration_seconds=analysis.duration,
                success=True,
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            return PipelineResult(
                output_path=output_path,
                events_detected=0,
                commentary_lines=0,
                duration_seconds=0,
                success=False,
                error=str(e),
            )
