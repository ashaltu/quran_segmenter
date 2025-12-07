# quran_segmenter/pipeline/jumlize.py
"""
Jumlize integration for LLM-based translation segmentation.
"""
import json
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from ..config import Config, TranslationConfig
from ..exceptions import JumlizeError

logger = logging.getLogger(__name__)


class JumlizeProcessor:
    """Handles LLM-based translation text segmentation."""
    
    def __init__(self, config: Config):
        self.config = config
        
        if not self.config.jumlize_binary.exists():
            raise JumlizeError(f"Jumlize binary not found at {self.config.jumlize_binary}")
    
    def is_segmented(self, translation_id: str) -> bool:
        """Check if translation has been segmented."""
        tc = self.config.get_translation(translation_id)
        if not tc.is_segmented:
            return False
        if tc.segmented_file_path and tc.segmented_file_path.exists():
            return self._validate_segmentation(tc.segmented_file_path)
        return False
    
    def _validate_segmentation(self, path: Path) -> bool:
        """Validate that segmentation file has segments for all verses."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check that verses have segments
            for verse_key, verse_data in data.items():
                if "segments" not in verse_data:
                    return False
            return True
        except Exception:
            return False
    
    def segment(
        self,
        translation_id: str,
        api_key: Optional[str] = None,
        force: bool = False
    ) -> Path:
        """
        Run jumlize segmentation on a translation.
        
        Args:
            translation_id: ID of registered translation
            api_key: Gemini API key (or from config/env)
            force: Force re-segmentation even if already done
            
        Returns:
            Path to segmented translation file
        """
        tc = self.config.get_translation(translation_id)
        
        # Check if already done
        if not force and self.is_segmented(translation_id):
            logger.info(f"Translation {translation_id} already segmented")
            return tc.segmented_file_path
        
        # Resolve API key
        api_key = api_key or self.config.jumlize.api_key
        if not api_key:
            import os
            api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            raise JumlizeError(
                "No API key provided. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        # Prepare output path
        output_path = self.config.translations_dir / f"{translation_id}_segmented.json"
        
        # Copy source to working location if needed
        working_copy = self.config.translations_dir / f"{translation_id}_working.json"
        shutil.copy(tc.file_path, working_copy)
        
        logger.info(f"Running jumlize segmentation for {translation_id}")
        logger.warning("This will make LLM API calls and may take significant time/cost.")
        
        # Build command
        cmd = [
            str(self.config.jumlize_binary),
            "segment",
            f"-api_key={api_key}",
            f"-translation={working_copy}",
            f"-model={self.config.jumlize.model}",
            f"-thinking_budget={self.config.jumlize.thinking_budget}",
            f"-temperature={self.config.jumlize.temperature}"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.config.base_dir),
                capture_output=True,
                text=True,
                timeout=7200  # 2 hour timeout for full Quran
            )
            
            if result.returncode != 0:
                logger.error(f"Jumlize stderr: {result.stderr}")
                raise JumlizeError(f"Jumlize failed: {result.stderr}")
            
            logger.debug(f"Jumlize stdout: {result.stdout}")
            
        except subprocess.TimeoutExpired:
            raise JumlizeError("Jumlize timed out after 2 hours")
        
        # Jumlize modifies the input file in place
        if working_copy.exists():
            shutil.move(working_copy, output_path)
        
        # Validate output
        if not self._validate_segmentation(output_path):
            raise JumlizeError(
                f"Segmentation incomplete. Some verses may have failed. "
                f"Check {output_path} and re-run with higher model settings."
            )
        
        # Update config
        self.config.update_translation_status(
            translation_id,
            is_segmented=True,
            segmented_file_path=output_path
        )
        
        logger.info(f"Segmentation complete: {output_path}")
        return output_path
    
    def get_segmentation_status(self, translation_id: str) -> Dict[str, Any]:
        """Get detailed segmentation status."""
        tc = self.config.get_translation(translation_id)
        
        status = {
            "translation_id": translation_id,
            "is_segmented": tc.is_segmented,
            "segmented_file": str(tc.segmented_file_path) if tc.segmented_file_path else None,
            "source_file": str(tc.file_path)
        }
        
        if tc.segmented_file_path and tc.segmented_file_path.exists():
            with open(tc.segmented_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            total = len(data)
            segmented = sum(1 for v in data.values() if "segments" in v)
            status["total_verses"] = total
            status["segmented_verses"] = segmented
            status["missing_verses"] = total - segmented
            status["completion_pct"] = round(100 * segmented / total, 1) if total > 0 else 0
        
        return status