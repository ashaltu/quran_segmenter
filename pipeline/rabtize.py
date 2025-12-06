# quran_segmenter/pipeline/rabtize.py
"""
Rabtize integration for embedding generation and alignment.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict
import logging

from ..config import Config, TranslationConfig
from ..models import VerseRange
from ..utils.cache import CacheManager
from ..exceptions import RabtizeError, TranslationNotPreparedError

logger = logging.getLogger(__name__)


class RabtizeProcessor:
    """Handles embedding generation and translation-to-Arabic alignment."""
    
    def __init__(self, config: Config, cache: CacheManager):
        self.config = config
        self.cache = cache
        
        if not self.config.rabtize_dir.exists():
            raise RabtizeError(f"Rabtize directory not found: {self.config.rabtize_dir}")
    
    def _run_rabtize(self, args: list, timeout: int = 3600) -> str:
        """Run rabtize command."""
        cmd = [
            sys.executable,
            "-m", "rabtize.main",
            f"--words={self.config.qpc_words_file}",
        ] + args
        
        logger.debug(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            cwd=str(self.config.rabtize_dir),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Rabtize stderr: {result.stderr}")
            raise RabtizeError(f"Rabtize command failed: {result.stderr}")
        
        return result.stdout
    
    def generate_spans_embeddings(self, force: bool = False) -> Path:
        """
        Generate span embeddings (one-time, reusable across translations).
        
        These are embeddings for all possible word ranges in the Quran text.
        Takes ~1-2 hours on GPU.
        """
        output_path = self.config.spans_embeddings_path
        
        if not force and output_path.exists():
            logger.info(f"Spans embeddings already exist: {output_path}")
            return output_path
        
        logger.info("Generating spans embeddings (this takes ~1-2 hours on GPU)...")
        
        # Need a translation file for the command, use any available
        translation_file = None
        for tc in self.config.translations.values():
            if tc.file_path.exists():
                translation_file = tc.file_path
                break
        
        if not translation_file:
            raise RabtizeError("No translation file available for spans generation")
        
        args = [
            f"--translation={translation_file}",
            "embed", "spans",
            str(output_path),
            f"--device={self.config.rabtize.device}",
            f"--batch_size={self.config.rabtize.batch_size}",
            f"--model={self.config.rabtize.embedding_model}"
        ]
        
        self._run_rabtize(args, timeout=14400)  # 4 hour timeout
        
        if not output_path.exists():
            raise RabtizeError("Spans embeddings generation failed - no output file")
        
        self.config.spans_embeddings_generated = True
        self.config.save()
        
        logger.info(f"Spans embeddings generated: {output_path}")
        return output_path
    
    def generate_segment_embeddings(
        self,
        translation_id: str,
        force: bool = False
    ) -> Path:
        """
        Generate segment embeddings for a translation.
        
        Must be run after jumlize segmentation.
        Takes ~30-60 seconds on GPU.
        """
        tc = self.config.get_translation(translation_id)
        
        # Check prerequisites
        if not tc.is_segmented or not tc.segmented_file_path:
            raise TranslationNotPreparedError(translation_id, "segmentation")
        
        output_path = self.config.embeddings_dir / f"{translation_id}.npz"
        
        if not force and output_path.exists():
            logger.info(f"Segment embeddings already exist: {output_path}")
            return output_path
        
        logger.info(f"Generating segment embeddings for {translation_id}...")
        
        args = [
            f"--translation={tc.segmented_file_path}",
            "embed", "segments",
            str(output_path),
            f"--device={self.config.rabtize.device}",
            f"--batch_size={self.config.rabtize.batch_size}",
            f"--model={self.config.rabtize.embedding_model}"
        ]
        
        self._run_rabtize(args, timeout=600)  # 10 minute timeout
        
        if not output_path.exists():
            raise RabtizeError(f"Segment embeddings generation failed for {translation_id}")
        
        self.config.update_translation_status(translation_id, embeddings_path=output_path)
        
        logger.info(f"Segment embeddings generated: {output_path}")
        return output_path
    
    def align(
        self,
        translation_id: str,
        verse_range: Optional[VerseRange] = None,
        use_cache: bool = True
    ) -> Dict:
        """
        Align translation segments to Arabic word ranges.
        
        Args:
            translation_id: ID of prepared translation
            verse_range: Optional specific verse range (None = all verses)
            use_cache: Whether to use cached alignments
            
        Returns:
            Alignment dictionary {verse_key: {segments: [...]}}
        """
        tc = self.config.get_translation(translation_id)
        
        # Check prerequisites
        if not tc.is_segmented or not tc.segmented_file_path:
            raise TranslationNotPreparedError(translation_id, "segmentation")
        if not tc.embeddings_path or not tc.embeddings_path.exists():
            raise TranslationNotPreparedError(translation_id, "segment embeddings")
        if not self.config.spans_embeddings_path.exists():
            raise TranslationNotPreparedError(translation_id, "spans embeddings")
        
        verse_range_str = str(verse_range) if verse_range else "all"
        
        # Check cache
        if use_cache:
            cached = self.cache.get_cached_alignment(translation_id, verse_range_str)
            if cached:
                logger.info(f"Using cached alignment for {translation_id} {verse_range_str}")
                return cached
        
        logger.info(f"Running alignment for {translation_id}...")
        
        # Create temp output file
        output_path = self.config.cache_dir / f"align_{translation_id}_{verse_range_str.replace(':', '_')}.json"
        
        args = [
            f"--translation={tc.segmented_file_path}",
            "align",
            f"-sp={self.config.spans_embeddings_path}",
            f"-se={tc.embeddings_path}",
            str(output_path)
        ]
        
        self._run_rabtize(args, timeout=300)
        
        if not output_path.exists():
            raise RabtizeError(f"Alignment failed - no output file")
        
        with open(output_path, "r", encoding="utf-8") as f:
            alignment = json.load(f)
        
        # Filter to verse range if specified
        if verse_range:
            verse_keys = set(verse_range.verse_keys())
            alignment = {k: v for k, v in alignment.items() if k in verse_keys}
        
        # Cache result
        if use_cache:
            self.cache.cache_alignment(translation_id, verse_range_str, alignment)
        
        logger.info(f"Alignment complete: {len(alignment)} verses")
        return alignment
    
    def is_ready(self, translation_id: str) -> tuple[bool, list[str]]:
        """Check if translation is ready for alignment."""
        missing = []
        
        tc = self.config.get_translation(translation_id)
        
        if not tc.is_segmented:
            missing.append("segmentation (run jumlize)")
        
        if not self.config.spans_embeddings_path.exists():
            missing.append("spans embeddings")
        
        if not tc.embeddings_path or not tc.embeddings_path.exists():
            missing.append("segment embeddings")
        
        return len(missing) == 0, missing