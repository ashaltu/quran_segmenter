# quran_segmenter/models.py
"""
Data models for the pipeline.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from pathlib import Path


@dataclass
class VerseRange:
    """Represents a range of verses within a single surah (optionally with preface phrases)."""
    surah: int
    start_verse: int
    end_verse: int
    include_basmalah: bool = False
    include_taawwudh: bool = False
    
    def __str__(self) -> str:
        base = f"{self.surah}:{self.start_verse}" if self.start_verse == self.end_verse else f"{self.surah}:{self.start_verse}-{self.end_verse}"
        prefixes = []
        if self.include_taawwudh:
            prefixes.append("taawwudh")
        if self.include_basmalah:
            prefixes.append("basmalah")
        return "+".join(prefixes + [base]) if prefixes else base
    
    def to_lafzize_format(self) -> str:
        """
        Format for lafzize API (flattened).
        For multi-segment requests this is a comma-joined view of `to_lafzize_segments()`.
        """
        segments = self.to_lafzize_segments()
        return ",".join(segments)
    
    def to_lafzize_segments(self) -> List[str]:
        """Segments list for lafzize API (preserves ordering)."""
        segments = []
        if self.include_taawwudh:
            segments.append("taawwudh")
        if self.include_basmalah:
            segments.append("basmalah")
        segments.append(f"{self.surah}:{self.start_verse},{self.surah}:{self.end_verse}")
        return segments
    
    def verse_keys(self) -> List[str]:
        """Get all verse keys in this range (phrases excluded)."""
        return [f"{self.surah}:{v}" for v in range(self.start_verse, self.end_verse + 1)]
    
    @classmethod
    def parse(cls, spec: str) -> "VerseRange":
        """
        Parse verse specification.
        Formats:
          - "2:282" -> single verse
          - "2:1-5" -> verse range
          - "2" -> entire surah (requires metadata)
        """
        spec = spec.strip()
        
        if ":" not in spec:
            # Full surah - will need metadata to resolve
            raise ValueError(f"Full surah spec '{spec}' requires metadata resolution")
        
        parts = spec.split(":")
        surah = int(parts[0])
        verse_part = parts[1]
        
        if "-" in verse_part:
            start, end = map(int, verse_part.split("-"))
        else:
            start = end = int(verse_part)
        
        return cls(surah=surah, start_verse=start, end_verse=end)
    
    @classmethod
    def from_surah(cls, surah: int, total_verses: int) -> "VerseRange":
        """Create range for entire surah."""
        return cls(surah=surah, start_verse=1, end_verse=total_verses)


@dataclass
class WordTimestamp:
    """Timestamp for a single word."""
    surah: int
    ayah: int
    word_index: int
    start_time: float
    end_time: float
    
    @property
    def key(self) -> Tuple[int, int, int]:
        return (self.surah, self.ayah, self.word_index)
    
    def to_dict(self) -> dict:
        return {
            "surah": self.surah,
            "ayah": self.ayah,
            "word_index": self.word_index,
            "start_time": self.start_time,
            "end_time": self.end_time
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WordTimestamp":
        return cls(
            surah=int(data["surah"]),
            ayah=int(data["ayah"]),
            word_index=int(data["word_index"]),
            start_time=float(data["start_time"]),
            end_time=float(data["end_time"])
        )
    
    @classmethod
    def from_lafzize_response(cls, item: dict) -> Optional["WordTimestamp"]:
        """Parse from lafzize API response item."""
        if item.get("type") != "word":
            return None
        key_parts = item["key"].split(":")
        return cls(
            surah=int(key_parts[0]),
            ayah=int(key_parts[1]),
            word_index=int(key_parts[2]),
            start_time=item["start"] / 1000.0,
            end_time=item["end"] / 1000.0
        )


@dataclass
class Segment:
    """A segment of a verse with timing and text."""
    start: float
    end: float
    arabic: str
    translation: str
    is_last: bool = False
    
    def to_dict(self) -> dict:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "arabic": self.arabic,
            "translation": self.translation,
            "is_last": self.is_last
        }


@dataclass
class VerseSegments:
    """All segments for a single verse."""
    verse_key: str
    segments: List[Segment] = field(default_factory=list)
    
    def to_dict(self) -> List[dict]:
        return [s.to_dict() for s in self.segments]


@dataclass
class ProcessingResult:
    """Result of processing a verse range."""
    verse_range: VerseRange
    verses: Dict[str, VerseSegments] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {vk: vs.to_dict() for vk, vs in self.verses.items()}
    
    def save(self, path: Path):
        """Save result to JSON file."""
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


@dataclass
class QuranMetadata:
    """Quran surah metadata."""
    surah_verse_counts: Dict[int, int] = field(default_factory=dict)
    
    @classmethod
    def load(cls, path: Path) -> "QuranMetadata":
        """Load from metadata file."""
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Handle different metadata formats
        verse_counts = {}
        if isinstance(data, dict):
            for key, value in data.items():
                if ":" in key:
                    surah = int(key.split(":")[0])
                    if surah not in verse_counts:
                        verse_counts[surah] = 0
                    verse_counts[surah] = max(verse_counts[surah], int(key.split(":")[1]))
                elif key.isdigit():
                    verse_counts[int(key)] = value.get("verses", value.get("ayahs", 0))
        
        return cls(surah_verse_counts=verse_counts)
    
    def get_verse_count(self, surah: int) -> int:
        """Get number of verses in a surah."""
        if surah not in self.surah_verse_counts:
            raise ValueError(f"Unknown surah: {surah}")
        return self.surah_verse_counts[surah]
