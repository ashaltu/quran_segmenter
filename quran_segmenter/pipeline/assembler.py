# quran_segmenter/pipeline/assembler.py
"""
Final segment assembly combining timings with aligned text.
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

from ..config import Config
from ..models import (
    VerseRange, WordTimestamp, Segment, VerseSegments, ProcessingResult
)

logger = logging.getLogger(__name__)


class SegmentAssembler:
    """Assembles final timed segments from component outputs."""
    
    def __init__(self, config: Config):
        self.config = config
        self._words_cache: Optional[Dict] = None
    
    @property
    def words_data(self) -> Dict:
        """Lazy load QPC words data."""
        if self._words_cache is None:
            with open(self.config.qpc_words_file, "r", encoding="utf-8") as f:
                self._words_cache = json.load(f)
        return self._words_cache
    
    def _get_arabic_words(self, surah: int, ayah: int) -> List[str]:
        """Get Arabic words for a verse."""
        words = []
        for key, word_data in self.words_data.items():
            if int(word_data.get("surah", 0)) == surah and int(word_data.get("ayah", 0)) == ayah:
                words.append((int(word_data.get("word", 0)), word_data.get("text", "")))
        
        # Sort by word index and return just text
        words.sort(key=lambda x: x[0])
        return [w[1] for w in words]
    
    def _build_timings_dict(
        self,
        timestamps: List[WordTimestamp]
    ) -> Dict[Tuple[int, int, int], Tuple[float, float]]:
        """Convert timestamp list to lookup dictionary."""
        return {ts.key: (ts.start_time, ts.end_time) for ts in timestamps}
    
    def assemble(
        self,
        verse_range: VerseRange,
        timestamps: List[WordTimestamp],
        alignment: Dict,
    ) -> ProcessingResult:
        """
        Assemble final segments.
        
        Args:
            verse_range: Range of verses being processed
            timestamps: Word-level timestamps from lafzize
            alignment: Segment-to-word alignment from rabtize
            
        Returns:
            ProcessingResult with all verse segments
        """
        result = ProcessingResult(verse_range=verse_range)
        timings = self._build_timings_dict(timestamps)
        
        for verse_key in verse_range.verse_keys():
            if verse_key not in alignment:
                result.warnings.append(f"No alignment data for {verse_key}")
                continue
            
            verse_data = alignment[verse_key]
            surah, ayah = map(int, verse_key.split(":"))
            arabic_words = self._get_arabic_words(surah, ayah)
            
            if not arabic_words:
                result.warnings.append(f"No Arabic words found for {verse_key}")
                continue
            
            segments = []
            raw_segments = verse_data.get("segments", [])
            
            for seg_data in raw_segments:
                word_range = seg_data.get("word_range")
                if not word_range:
                    continue
                
                start_idx = word_range.get("start", 1)
                end_idx = word_range.get("end", 1)
                
                # Get Arabic text for this segment
                # Word indices are 1-based
                arabic_text = " ".join(arabic_words[start_idx - 1:end_idx])
                
                # Get timing for this word range
                word_times = []
                for word_idx in range(start_idx, end_idx + 1):
                    key = (surah, ayah, word_idx)
                    if key in timings:
                        word_times.append(timings[key])
                
                if not word_times:
                    result.warnings.append(
                        f"No timing data for {verse_key} words {start_idx}-{end_idx}"
                    )
                    continue
                
                start_time = min(t[0] for t in word_times)
                end_time = max(t[1] for t in word_times)
                
                segment = Segment(
                    start=start_time,
                    end=end_time,
                    arabic=arabic_text,
                    translation=seg_data.get("t", ""),
                    is_last=False
                )
                segments.append(segment)
            
            if segments:
                segments[-1].is_last = True
                result.verses[verse_key] = VerseSegments(
                    verse_key=verse_key,
                    segments=segments
                )
            else:
                result.warnings.append(f"No valid segments for {verse_key}")
        
        return result