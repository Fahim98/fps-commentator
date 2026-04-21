"""
Tests for the Commentary Writer module.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.pipeline.commentary_writer import CommentaryWriter, CommentaryCue
from src.pipeline.video_analyzer import VideoAnalysis, GameEvent


def make_analysis(events: list[dict]) -> VideoAnalysis:
    return VideoAnalysis(
        game_title="Valorant",
        duration=60.0,
        overall_summary="An intense clutch round.",
        events=[GameEvent(**e) for e in events],
    )


@pytest.fixture
def sample_events():
    return [
        {"timestamp_seconds": 5.0, "event_type": "kill", "description": "Headshot with Vandal", "intensity": 8, "commentable": True},
        {"timestamp_seconds": 12.0, "event_type": "kill", "description": "Second kill", "intensity": 6, "commentable": True},
        {"timestamp_seconds": 20.0, "event_type": "multi_kill", "description": "Triple kill", "intensity": 10, "commentable": True},
        {"timestamp_seconds": 35.0, "event_type": "death", "description": "Killed by enemy", "intensity": 3, "commentable": False},
        {"timestamp_seconds": 55.0, "event_type": "round_end", "description": "Round win", "intensity": 7, "commentable": True},
    ]


class TestCommentaryWriter:

    def test_filter_by_density_full(self, sample_events):
        writer = CommentaryWriter.__new__(CommentaryWriter)
        writer.persona = "hype_caster"
        analysis = make_analysis(sample_events)
        events = analysis.highlight_events   # Already filters commentable=False
        filtered = writer._filter_by_density(events, density=1.0)
        assert len(filtered) == 4  # All commentable events

    def test_filter_by_density_sparse(self, sample_events):
        writer = CommentaryWriter.__new__(CommentaryWriter)
        writer.persona = "hype_caster"
        analysis = make_analysis(sample_events)
        events = analysis.highlight_events
        filtered = writer._filter_by_density(events, density=0.3)
        # intensity >= 7 are always kept: timestamps 5.0 (8), 20.0 (10), 55.0 (7)
        timestamps = [e.timestamp_seconds for e in filtered]
        assert 20.0 in timestamps  # intensity 10, always kept
        assert 5.0 in timestamps   # intensity 8, always kept

    def test_parse_valid_json(self):
        writer = CommentaryWriter.__new__(CommentaryWriter)
        json_response = '''[
            {"timestamp_seconds": 5.0, "text": "WHAT A SHOT!", "pause_before_seconds": 0.3},
            {"timestamp_seconds": 20.0, "text": "TRIPLE KILL!", "pause_before_seconds": 0.5}
        ]'''
        cues = writer._parse_response(json_response)
        assert len(cues) == 2
        assert cues[0].text == "WHAT A SHOT!"
        assert cues[0].speak_at_seconds == pytest.approx(5.3)
        assert cues[1].speak_at_seconds == pytest.approx(20.5)

    def test_parse_markdown_wrapped_json(self):
        writer = CommentaryWriter.__new__(CommentaryWriter)
        wrapped = '```json\n[{"timestamp_seconds": 1.0, "text": "Nice!", "pause_before_seconds": 0.2}]\n```'
        cues = writer._parse_response(wrapped)
        assert len(cues) == 1
        assert cues[0].text == "Nice!"

    def test_invalid_persona_raises(self):
        with pytest.raises(ValueError, match="Unknown persona"):
            CommentaryWriter(persona="robo_caster")

    def test_highlight_events_excludes_non_commentable(self, sample_events):
        analysis = make_analysis(sample_events)
        timestamps = [e.timestamp_seconds for e in analysis.highlight_events]
        assert 35.0 not in timestamps  # commentable=False event excluded

    def test_highlight_events_sorted(self, sample_events):
        analysis = make_analysis(sample_events)
        ts = [e.timestamp_seconds for e in analysis.highlight_events]
        assert ts == sorted(ts)
