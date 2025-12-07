# quran_segmenter/pipeline/orchestrator.py
"""
Main pipeline orchestrator that coordinates all components.
"""
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from ..config import Config, get_config
from ..models import VerseRange, ProcessingResult
from ..utils.cache import CacheManager
from ..utils.verse_parser import parse_verse_spec, load_quran_metadata
from ..exceptions import (
    QuranSegmenterError, TranslationNotPreparedError, ConfigurationError
)

from .lafzize import LafzizeProcessor
from .jumlize import JumlizeProcessor
from .rabtize import RabtizeProcessor
from .assembler import SegmentAssembler

logger = logging.getLogger(__name__)


class QuranSegmenterPipeline:
    """
    Main orchestrator for the Quran segmentation pipeline.
    
    Usage:
        pipeline = QuranSegmenterPipeline()
        
        # One-time setup per translation
        pipeline.prepare_translation("en-sahih", api_key="...")
        
        # Process audio
        result = pipeline.process(
            audio_path="recitation.mp3",
            verses="2:282",
            translation_id="en-sahih"
        )
        result.save("output.json")
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.cache = CacheManager(self.config.cache_dir)
        self.metadata = load_quran_metadata(self.config.quran_metadata_file)
        
        # Initialize processors lazily
        self._lafzize: Optional[LafzizeProcessor] = None
        self._jumlize: Optional[JumlizeProcessor] = None
        self._rabtize: Optional[RabtizeProcessor] = None
        self._assembler: Optional[SegmentAssembler] = None
    
    @property
    def lafzize(self) -> LafzizeProcessor:
        if self._lafzize is None:
            self._lafzize = LafzizeProcessor(self.config, self.cache)
        return self._lafzize
    
    @property
    def jumlize(self) -> JumlizeProcessor:
        if self._jumlize is None:
            self._jumlize = JumlizeProcessor(self.config)
        return self._jumlize
    
    @property
    def rabtize(self) -> RabtizeProcessor:
        if self._rabtize is None:
            self._rabtize = RabtizeProcessor(self.config, self.cache)
        return self._rabtize
    
    @property
    def assembler(self) -> SegmentAssembler:
        if self._assembler is None:
            self._assembler = SegmentAssembler(self.config)
        return self._assembler
    
    # -------------------------------------------------------------------------
    # Translation Management
    # -------------------------------------------------------------------------
    
    def register_translation(
        self,
        translation_id: str,
        name: str,
        language_code: str,
        source_file: Path
    ) -> None:
        """Register a new translation for processing."""
        self.config.register_translation(
            translation_id=translation_id,
            name=name,
            language_code=language_code,
            source_file=source_file,
            copy_to_data_dir=True
        )
        logger.info(f"Registered translation: {translation_id}")
    
    def list_translations(self) -> List[Dict[str, Any]]:
        """List all registered translations with their status."""
        result = []
        for tid, tc in self.config.translations.items():
            ready, missing = self.rabtize.is_ready(tid) if tc.is_segmented else (False, ["segmentation"])
            result.append({
                "id": tid,
                "name": tc.name,
                "language": tc.language_code,
                "is_segmented": tc.is_segmented,
                "has_embeddings": tc.embeddings_path is not None and tc.embeddings_path.exists(),
                "ready_for_processing": ready,
                "missing": missing if not ready else []
            })
        return result
    
    # -------------------------------------------------------------------------
    # Preparation Steps (One-time per translation)
    # -------------------------------------------------------------------------
    
    def prepare_translation(
        self,
        translation_id: str,
        api_key: Optional[str] = None,
        skip_segmentation: bool = False,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Fully prepare a translation for processing.
        
        This runs:
        1. Jumlize segmentation (if not done, uses LLM)
        2. Spans embeddings (if not done, one-time)
        3. Segment embeddings (if not done)
        
        Args:
            translation_id: ID of registered translation
            api_key: Gemini API key for jumlize (if needed)
            skip_segmentation: Skip jumlize if translation is pre-segmented
            force: Force re-run of all steps
            
        Returns:
            Status dictionary with results
        """
        status = {"translation_id": translation_id, "steps": {}}
        
        tc = self.config.get_translation(translation_id)
        
        # Step 1: Segmentation
        if skip_segmentation:
            logger.info(f"Skipping segmentation for {translation_id} (pre-segmented)")
            status["steps"]["segmentation"] = "skipped"
            # Mark as segmented if source file has segments
            if not tc.is_segmented:
                self.config.update_translation_status(
                    translation_id,
                    is_segmented=True,
                    segmented_file_path=tc.file_path
                )
        elif tc.is_segmented and not force:
            logger.info(f"Segmentation already done for {translation_id}")
            status["steps"]["segmentation"] = "already_done"
        else:
            logger.info(f"Running segmentation for {translation_id}")
            try:
                self.jumlize.segment(translation_id, api_key=api_key, force=force)
                status["steps"]["segmentation"] = "completed"
            except Exception as e:
                status["steps"]["segmentation"] = f"failed: {e}"
                raise
        
        # Step 2: Spans embeddings (global, one-time)
        if self.config.spans_embeddings_generated and not force:
            logger.info("Spans embeddings already exist")
            status["steps"]["spans_embeddings"] = "already_done"
        else:
            logger.info("Generating spans embeddings...")
            try:
                self.rabtize.generate_spans_embeddings(force=force)
                status["steps"]["spans_embeddings"] = "completed"
            except Exception as e:
                status["steps"]["spans_embeddings"] = f"failed: {e}"
                raise
        
        # Step 3: Segment embeddings
        tc = self.config.get_translation(translation_id)  # Refresh
        if tc.embeddings_path and tc.embeddings_path.exists() and not force:
            logger.info(f"Segment embeddings already exist for {translation_id}")
            status["steps"]["segment_embeddings"] = "already_done"
        else:
            logger.info(f"Generating segment embeddings for {translation_id}...")
            try:
                self.rabtize.generate_segment_embeddings(translation_id, force=force)
                status["steps"]["segment_embeddings"] = "completed"
            except Exception as e:
                status["steps"]["segment_embeddings"] = f"failed: {e}"
                raise
        
        status["ready"] = True
        logger.info(f"Translation {translation_id} is ready for processing")
        return status
    
    # -------------------------------------------------------------------------
    # Main Processing
    # -------------------------------------------------------------------------
    
    def process(
        self,
        audio_path: Path,
        verses: str,
        translation_id: str,
        output_path: Optional[Path] = None,
        use_cache: bool = True
    ) -> ProcessingResult:
        """
        Process audio and generate timed segments.
        
        Args:
            audio_path: Path to audio file
            verses: Verse specification (e.g., "2:282", "2:1-10", "2")
            translation_id: ID of prepared translation
            output_path: Optional path to save result
            use_cache: Whether to use cached intermediate results
            
        Returns:
            ProcessingResult with timed segments
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Parse verse specification
        verse_range = parse_verse_spec(verses, self.metadata)
        logger.info(f"Processing {audio_path.name} for verses {verse_range}")
        
        # Verify translation is ready
        ready, missing = self.rabtize.is_ready(translation_id)
        if not ready:
            raise TranslationNotPreparedError(translation_id, ", ".join(missing))
        
        # Step 1: Get word timestamps
        logger.info("Step 1/3: Getting word timestamps (lafzize)")
        timestamps = self.lafzize.process(
            audio_path=audio_path,
            verse_range=verse_range,
            use_cache=use_cache
        )
        
        # Step 2: Get alignment
        logger.info("Step 2/3: Getting alignment (rabtize)")
        alignment = self.rabtize.align(
            translation_id=translation_id,
            verse_range=verse_range,
            use_cache=use_cache
        )
        
        # Step 3: Assemble final segments
        logger.info("Step 3/3: Assembling segments")
        result = self.assembler.assemble(
            verse_range=verse_range,
            timestamps=timestamps,
            alignment=alignment
        )
        
        # Save if output path provided
        if output_path:
            result.save(output_path)
            logger.info(f"Result saved to {output_path}")
        
        # Log summary
        logger.info(
            f"Processed {len(result.verses)} verses, "
            f"{sum(len(vs.segments) for vs in result.verses.values())} total segments"
        )
        if result.warnings:
            for w in result.warnings:
                logger.warning(w)
        
        return result
    
    def cleanup(self):
        """Cleanup resources (stop servers, etc.)."""
        if self._lafzize:
            self._lafzize.stop_server()