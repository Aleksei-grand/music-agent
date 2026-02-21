"""
Audio processor tests
"""
import pytest
from pathlib import Path

from music_agent.audio.processor import AudioProcessor


class TestAudioProcessor:
    def test_init(self):
        processor = AudioProcessor()
        assert processor.ffmpeg == "ffmpeg"
        assert processor.ffprobe == "ffprobe"
    
    def test_get_info_not_found(self):
        processor = AudioProcessor()
        info = processor.get_info(Path("/nonexistent/file.mp3"))
        
        assert "error" in info
    
    def test_validate_for_distribution_not_found(self):
        processor = AudioProcessor()
        result = processor.validate_for_distribution(Path("/nonexistent/file.mp3"))
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
