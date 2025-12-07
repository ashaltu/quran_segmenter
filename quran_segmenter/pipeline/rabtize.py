# quran_segmenter/pipeline/rabtize.py
"""
Rabtize integration for embedding generation and alignment.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Tuple
import logging

from ..config import Config, TranslationConfig
from ..models import VerseRange
from ..utils.cache import CacheManager
from ..utils.progress import ProgressReporter
from ..exceptions import RabtizeError, TranslationNotPreparedError

logger = logging.getLogger(__name__)


class RabtizeProcessor:
    """Handles embedding generation and translation-to-Arabic alignment."""
    
    def __init__(self, config: Config, cache: CacheManager):
        self.config = config
        self.cache = cache
        
        if not self.config.rabtize_dir.exists():
            raise RabtizeError(f"Rabtize directory not found: {self.config.rabtize_dir}")
    
    def _run_rabtize_with_progress(
        self,
        args: list,
        desc: str,
        timeout: int = 14400
    ) -> str:
        """Run rabtize command with progress output."""
        # Copy required files to rabtize directory
        qpc_dst = self.config.rabtize_dir / "qpc-hafs-word-by-word.json"
        if not qpc_dst.exists() and self.config.qpc_words_file.exists():
            import shutil
            shutil.copy(self.config.qpc_words_file, qpc_dst)
        
        cmd = [
            sys.executable,
            "-m", "rabtize.main",
            f"--words=qpc-hafs-word-by-word.json",
        ] + args
        
        logger.info(f"Running: {' '.join(cmd)}")
        print(f"\n{desc}")
        print("-" * 50)
        
        process = subprocess.Popen(
            cmd,
            cwd=str(self.config.rabtize_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        output_lines = []
        batch_count = 0
        total_batches = None
        
        for line in iter(process.stdout.readline, ''):
            output_lines.append(line)
            
            # Parse progress from rabtize output
            if "Batches:" in line or "%" in line:
                print(f"\r  {line.strip()}", end="", flush=True)
            elif "Generating" in line or "Loading" in line or "Saving" in line:
                print(f"  {line.strip()}")
            
            # Check for errors
            if "error" in line.lower() or "exception" in line.lower():
                logger.warning(line.strip())
        
        process.wait()
        print()  # New line after progress
        
        if process.returncode != 0:
            full_output = "".join(output_lines)
            logger.error(f"Rabtize failed:\n{full_output[-2000:]}")
            raise RabtizeError(f"Rabtize command failed (exit code {process.returncode})")
        
        return "".join(output_lines)
    
    def generate_spans_embeddings(self, force: bool = False) -> Path:
        """
        Generate span embeddings (one-time, reusable across translations).
        
        These are embeddings for all possible word ranges in the Quran text.
        Takes ~1-2 hours on GPU.
        """
        output_path = self.config.spans_embeddings_path
        
        if not force and output_path.exists():
            logger.info(f"✓ Spans embeddings already exist: {output_path}")
            return output_path
        
        # Need a translation file for the command
        translation_file = None
        for tc in self.config.translations.values():
            if Path(tc.file_path).exists():
                translation_file = tc.file_path
                break
        
        if not translation_file:
            # Create a minimal dummy file
            dummy = self.config.translations_dir / "_dummy.json"
            dummy.write_text('{"1:1": {"text": "test"}}')
            translation_file = str(dummy)
        
        # Copy translation to rabtize dir
        import shutil
        trans_name = Path(translation_file).name
        trans_dst = self.config.rabtize_dir / trans_name
        if not trans_dst.exists():
            shutil.copy(translation_file, trans_dst)
        
        args = [
            f"--translation={trans_name}",
            "embed", "spans",
            str(output_path),
            f"--device={self.config.rabtize.device}",
            f"--batch_size={self.config.rabtize.batch_size}",
            f"--model={self.config.rabtize.embedding_model}"
        ]
        
        print("\n" + "=" * 60)
        print("GENERATING SPANS EMBEDDINGS")
        print("This is a one-time operation that takes 1-2 hours on GPU.")
        print("The embeddings will be reused for all translations.")
        print("=" * 60)
        
        self._run_rabtize_with_progress(
            args,
            "Generating ~700k span embeddings...",
            timeout=14400
        )
        
        if not output_path.exists():
            raise RabtizeError("Spans embeddings generation failed - no output file")
        
        self.config.spans_embeddings_generated = True
        self.config.save()
        
        print(f"✓ Spans embeddings saved to: {output_path}")
        print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
        
        return output_path
    
    def generate_segment_embeddings(
        self,
        translation_id: str,
        force: bool = False
    ) -> Path:
        """
        Generate segment embeddings for a translation.
        
        Must be run after jumlize segmentation.
        Takes ~1-5 minutes on GPU.
        """
        tc = self.config.get_translation(translation_id)
        
        # Check prerequisites
        if not tc.is_segmented:
            raise TranslationNotPreparedError(translation_id, "segmentation")
        
        segmented_path = tc.get_segmented_path() or tc.get_file_path()
        if not segmented_path.exists():
            raise FileNotFoundError(f"Segmented file not found: {segmented_path}")
        
        output_path = self.config.embeddings_dir / f"{translation_id}.npz"
        
        if not force and output_path.exists():
            logger.info(f"✓ Segment embeddings already exist: {output_path}")
            return output_path
        
        # Copy translation to rabtize dir
        import shutil
        trans_name = segmented_path.name
        trans_dst = self.config.rabtize_dir / trans_name
        shutil.copy(segmented_path, trans_dst)
        
        args = [
            f"--translation={trans_name}",
            "embed", "segments",
            str(output_path),
            f"--device={self.config.rabtize.device}",
            f"--batch_size={self.config.rabtize.batch_size}",
            f"--model={self.config.rabtize.embedding_model}"
        ]
        
        print(f"\nGenerating segment embeddings for {translation_id}...")
        
        self._run_rabtize_with_progress(
            args,
            f"Embedding segments for {translation_id}...",
            timeout=600
        )
        
        if not output_path.exists():
            raise RabtizeError(f"Segment embeddings generation failed for {translation_id}")
        
        self.config.update_translation(translation_id, embeddings_path=output_path)
        
        print(f"✓ Segment embeddings saved to: {output_path}")
        print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
        
        return output_path
    
    def align(
        self,
        translation_id: str,
        verse_range: Optional[VerseRange] = None,
        use_cache: bool = True
    ) -> Dict:
        """Align translation segments to Arabic word ranges."""
        tc = self.config.get_translation(translation_id)
        
        # Check prerequisites
        if not tc.is_segmented:
            raise TranslationNotPreparedError(translation_id, "segmentation")
        if not tc.embeddings_path or not Path(tc.embeddings_path).exists():
            raise TranslationNotPreparedError(translation_id, "segment embeddings")
        if not self.config.spans_embeddings_path.exists():
            raise TranslationNotPreparedError(translation_id, "spans embeddings (run generate_spans_embeddings first)")
        
        verse_range_str = str(verse_range) if verse_range else "all"
        
        # Check cache
        if use_cache:
            cached = self.cache.get_cached_alignment(translation_id, verse_range_str)
            if cached:
                logger.info(f"Using cached alignment for {translation_id} {verse_range_str}")
                return cached
        
        logger.info(f"Running alignment for {translation_id}...")
        
        # Copy files to rabtize dir
        import shutil
        segmented_path = tc.get_segmented_path() or tc.get_file_path()
        trans_name = segmented_path.name
        trans_dst = self.config.rabtize_dir / trans_name
        shutil.copy(segmented_path, trans_dst)
        
        output_path = self.config.cache_dir / f"align_{translation_id}_{verse_range_str.replace(':', '_').replace('-', '_')}.json"
        
        args = [
            f"--translation={trans_name}",
            "align",
            f"-sp={self.config.spans_embeddings_path}",
            f"-se={tc.embeddings_path}",
            str(output_path)
        ]
        
        self._run_rabtize_with_progress(args, "Aligning segments to Arabic...", timeout=300)
        
        if not output_path.exists():
            raise RabtizeError("Alignment failed - no output file")
        
        with open(output_path, "r", encoding="utf-8") as f:
            alignment = json.load(f)
        
        # Filter to verse range if specified
        if verse_range:
            verse_keys = set(verse_range.verse_keys())
            alignment = {k: v for k, v in alignment.items() if k in verse_keys}
        
        # Cache result
        if use_cache:
            self.cache.cache_alignment(translation_id, verse_range_str, alignment)
        
        logger.info(f"✓ Alignment complete: {len(alignment)} verses")
        return alignment
    
    def is_ready(self, translation_id: str) -> Tuple[bool, list]:
        """Check if translation is ready for alignment."""
        missing = []
        
        try:
            tc = self.config.get_translation(translation_id)
        except ValueError:
            return False, ["translation not registered"]
        
        if not tc.is_segmented:
            missing.append("segmentation")
        
        if not self.config.spans_embeddings_path.exists():
            missing.append("spans embeddings")
        
        if not tc.embeddings_path or not Path(tc.embeddings_path).exists():
            missing.append("segment embeddings")
        
        return len(missing) == 0, missing