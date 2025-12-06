# quran_segmenter/__init__.py
"""
Quran Segmenter - Generate timed subtitle segments for Quran recitations.
"""
from .config import Config, get_config
from .pipeline.orchestrator import QuranSegmenterPipeline
from .models import VerseRange, ProcessingResult, Segment

__version__ = "1.0.0"
__all__ = [
    "Config",
    "get_config",
    "QuranSegmenterPipeline",
    "VerseRange",
    "ProcessingResult",
    "Segment"
]