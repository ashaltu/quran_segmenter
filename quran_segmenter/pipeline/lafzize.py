# quran_segmenter/pipeline/lafzize.py
"""
Lafzize integration for audio-to-word timestamp alignment.
"""
import json
import requests
from pathlib import Path
from typing import List, Optional
import logging

from ..config import Config
from ..models import VerseRange, WordTimestamp
from ..utils.server import LafzizeServer
from ..utils.cache import CacheManager
from ..exceptions import LafzizeError, ServerNotRunningError

logger = logging.getLogger(__name__)


class LafzizeProcessor:
    """Handles audio-to-word timestamp alignment using lafzize."""
    
    def __init__(self, config: Config, cache: CacheManager):
        self.config = config
        self.cache = cache
        self.server = LafzizeServer(
            lafzize_dir=config.lafzize_dir,
            host=config.lafzize.server_host,
            port=config.lafzize.server_port
        )
    
    @property
    def api_url(self) -> str:
        return f"http://{self.config.lafzize.server_host}:{self.config.lafzize.server_port}/"
    
    def ensure_server(self) -> bool:
        """Ensure lafzize server is running."""
        return self.server.ensure_running()
    
    def process(
        self,
        audio_path: Path,
        verse_range: VerseRange,
        use_cache: bool = True
    ) -> List[WordTimestamp]:
        """
        Get word timestamps for audio file.
        
        Args:
            audio_path: Path to audio file
            verse_range: Range of verses in the audio
            use_cache: Whether to use cached results
            
        Returns:
            List of WordTimestamp objects
        """
        verse_range_str = str(verse_range)
        
        # Check cache first
        if use_cache:
            cached = self.cache.get_cached_timestamps(audio_path, verse_range_str)
            if cached:
                logger.info(f"Using cached timestamps for {verse_range_str}")
                return [WordTimestamp.from_dict(t) for t in cached]
        
        # Ensure server is running
        if not self.ensure_server():
            raise ServerNotRunningError("Could not start lafzize server")
        
        # Call lafzize API
        logger.info(f"Calling lafzize for {audio_path.name} verses {verse_range_str}")
        
        try:
            with open(audio_path, "rb") as f:
                files = {"audio": (audio_path.name, f, "audio/mpeg")}
                data = {"segments": verse_range.to_lafzize_format()}
                
                response = requests.post(
                    self.api_url,
                    files=files,
                    data=data,
                    timeout=self.config.lafzize.timeout
                )
            
            if response.status_code != 200:
                raise LafzizeError(
                    f"Lafzize API error {response.status_code}: {response.text}"
                )
            
            raw_timestamps = response.json()
            
        except requests.exceptions.RequestException as e:
            raise LafzizeError(f"Failed to connect to lafzize: {e}")
        
        # Parse response
        timestamps = []
        for item in raw_timestamps:
            ts = WordTimestamp.from_lafzize_response(item)
            if ts:
                timestamps.append(ts)
        
        logger.info(f"Got {len(timestamps)} word timestamps")
        
        # Cache results
        if use_cache:
            self.cache.cache_timestamps(
                audio_path,
                verse_range_str,
                [t.to_dict() for t in timestamps]
            )
        
        return timestamps
    
    def stop_server(self):
        """Stop the lafzize server if we started it."""
        self.server.stop()