# quran_segmenter/utils/verse_parser.py
"""
Verse specification parsing utilities.
"""
import json
from pathlib import Path
from typing import Dict, Tuple
import logging

from ..models import VerseRange, QuranMetadata

logger = logging.getLogger(__name__)

# Standard Quran structure (fallback)
SURAH_VERSE_COUNTS = {
    1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109,
    11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135,
    21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60,
    31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85,
    41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45,
    51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13,
    61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44,
    71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42,
    81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20,
    91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11,
    101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3,
    111: 5, 112: 4, 113: 5, 114: 6
}


def load_quran_metadata(path: Path) -> QuranMetadata:
    """Load Quran metadata from file or use defaults."""
    if path.exists():
        try:
            meta = QuranMetadata.load(path)
            # Fill missing surahs with fallback counts
            for s, count in SURAH_VERSE_COUNTS.items():
                if s not in meta.surah_verse_counts:
                    meta.surah_verse_counts[s] = count
            return meta
        except Exception as e:
            logger.warning(f"Failed to load metadata from {path}: {e}")
    
    return QuranMetadata(surah_verse_counts=SURAH_VERSE_COUNTS.copy())


def parse_verse_spec(
    spec: str,
    metadata: QuranMetadata = None
) -> VerseRange:
    """
    Parse a verse specification into a VerseRange.
    
    Formats supported:
      - "2:282" -> single verse
      - "2:1-5" -> verse range within surah
      - "2" -> entire surah (requires metadata)
      - "taawwudh+2:1-5" -> prepend taawwudh segment
      - "taawwudh+basmalah+2:1-5" -> prepend taawwudh and basmalah
      - "2:255,2:282" -> NOT supported (multiple non-contiguous)
    """
    spec = spec.strip()
    include_taawwudh = False
    include_basmalah = False
    
    # Extract optional prefix phrases
    if "+" in spec:
        parts = [p.strip() for p in spec.split("+") if p.strip()]
        if not parts:
            raise ValueError("Empty verse spec")
        base_spec = parts[-1]
        for prefix in parts[:-1]:
            key = prefix.lower()
            if key == "taawwudh":
                include_taawwudh = True
            elif key == "basmalah":
                include_basmalah = True
            else:
                raise ValueError(f"Unknown prefix '{prefix}' in verse spec '{spec}'")
    else:
        base_spec = spec
    
    # Check for unsupported formats
    if "," in base_spec and base_spec.count(":") > 1:
        raise ValueError(
            f"Non-contiguous verse ranges not supported: '{spec}'. "
            "Process each range separately."
        )
    
    if ":" not in base_spec:
        # Full surah
        surah = int(base_spec)
        if metadata:
            verse_count = metadata.get_verse_count(surah)
        elif surah in SURAH_VERSE_COUNTS:
            verse_count = SURAH_VERSE_COUNTS[surah]
        else:
            raise ValueError(f"Unknown surah {surah} and no metadata provided")
        
        return VerseRange(
            surah=surah,
            start_verse=1,
            end_verse=verse_count,
            include_basmalah=include_basmalah,
            include_taawwudh=include_taawwudh
        )
    
    vr = VerseRange.parse(base_spec)
    vr.include_basmalah = include_basmalah
    vr.include_taawwudh = include_taawwudh
    return vr


def validate_verse_range(vr: VerseRange, metadata: QuranMetadata = None) -> Tuple[bool, str]:
    """Validate a verse range against metadata."""
    if metadata:
        try:
            max_verse = metadata.get_verse_count(vr.surah)
            if vr.end_verse > max_verse:
                return False, f"Verse {vr.end_verse} exceeds surah {vr.surah} max ({max_verse})"
        except ValueError as e:
            return False, str(e)
    elif vr.surah in SURAH_VERSE_COUNTS:
        max_verse = SURAH_VERSE_COUNTS[vr.surah]
        if vr.end_verse > max_verse:
            return False, f"Verse {vr.end_verse} exceeds surah {vr.surah} max ({max_verse})"
    
    if vr.start_verse < 1:
        return False, "Start verse must be >= 1"
    
    if vr.start_verse > vr.end_verse:
        return False, "Start verse must be <= end verse"
    
    return True, ""
