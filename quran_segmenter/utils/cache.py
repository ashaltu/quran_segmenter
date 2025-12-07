# quran_segmenter/utils/cache.py
"""
Caching utilities for intermediate results.
"""
import json
import hashlib
from pathlib import Path
from typing import Optional, Any, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of intermediate processing results."""
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = cache_dir / "index.json"
        self._index = self._load_index()
    
    def _load_index(self) -> Dict[str, dict]:
        """Load cache index."""
        if self._index_path.exists():
            with open(self._index_path, "r") as f:
                return json.load(f)
        return {}
    
    def _save_index(self):
        """Save cache index."""
        with open(self._index_path, "w") as f:
            json.dump(self._index, f, indent=2)
    
    def _make_key(self, category: str, identifier: str) -> str:
        """Create a cache key."""
        return f"{category}:{identifier}"
    
    def _hash_content(self, content: str) -> str:
        """Create hash of content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get_timestamps_path(self, audio_hash: str, verse_range: str) -> Path:
        """Get path for cached timestamps."""
        safe_name = verse_range.replace(":", "_").replace("-", "_")
        return self.cache_dir / "timestamps" / f"{audio_hash}_{safe_name}.json"
    
    def get_alignment_path(self, translation_id: str, verse_range: str) -> Path:
        """Get path for cached alignment."""
        safe_name = verse_range.replace(":", "_").replace("-", "_")
        return self.cache_dir / "alignments" / f"{translation_id}_{safe_name}.json"
    
    def cache_timestamps(
        self,
        audio_path: Path,
        verse_range: str,
        timestamps: list
    ) -> Path:
        """Cache timestamp data."""
        # Create audio hash for cache key
        audio_hash = hashlib.md5(open(audio_path, 'rb').read()).hexdigest()[:12]
        
        cache_path = self.get_timestamps_path(audio_hash, verse_range)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(timestamps, f, indent=2, ensure_ascii=False)
        
        # Update index
        key = self._make_key("timestamps", f"{audio_hash}_{verse_range}")
        self._index[key] = {
            "path": str(cache_path),
            "audio_path": str(audio_path),
            "verse_range": verse_range,
            "created": datetime.now().isoformat(),
            "count": len(timestamps)
        }
        self._save_index()
        
        logger.debug(f"Cached timestamps: {cache_path}")
        return cache_path
    
    def get_cached_timestamps(
        self,
        audio_path: Path,
        verse_range: str
    ) -> Optional[list]:
        """Retrieve cached timestamps if available."""
        audio_hash = hashlib.md5(open(audio_path, 'rb').read()).hexdigest()[:12]
        cache_path = self.get_timestamps_path(audio_hash, verse_range)
        
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                logger.debug(f"Cache hit for timestamps: {cache_path}")
                return json.load(f)
        return None
    
    def cache_alignment(
        self,
        translation_id: str,
        verse_range: str,
        alignment: dict
    ) -> Path:
        """Cache alignment data."""
        cache_path = self.get_alignment_path(translation_id, verse_range)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(alignment, f, indent=2, ensure_ascii=False)
        
        key = self._make_key("alignment", f"{translation_id}_{verse_range}")
        self._index[key] = {
            "path": str(cache_path),
            "translation_id": translation_id,
            "verse_range": verse_range,
            "created": datetime.now().isoformat()
        }
        self._save_index()
        
        logger.debug(f"Cached alignment: {cache_path}")
        return cache_path
    
    def get_cached_alignment(
        self,
        translation_id: str,
        verse_range: str
    ) -> Optional[dict]:
        """Retrieve cached alignment if available."""
        cache_path = self.get_alignment_path(translation_id, verse_range)
        
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                logger.debug(f"Cache hit for alignment: {cache_path}")
                return json.load(f)
        return None
    
    def clear(self, category: Optional[str] = None):
        """Clear cache entries."""
        if category:
            keys_to_remove = [k for k in self._index if k.startswith(f"{category}:")]
            for key in keys_to_remove:
                entry = self._index[key]
                path = Path(entry["path"])
                if path.exists():
                    path.unlink()
                del self._index[key]
        else:
            # Clear all
            import shutil
            for subdir in self.cache_dir.iterdir():
                if subdir.is_dir() and subdir.name != "index.json":
                    shutil.rmtree(subdir)
            self._index = {}
        
        self._save_index()
        logger.info(f"Cache cleared: {category or 'all'}")