# quran_segmenter/colab/helpers.py
"""
Helper functions specifically for Google Colab environment.
"""
import os
import sys
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ColabEnvironment:
    """
    Manages the Colab environment setup and state.
    
    Usage:
        env = ColabEnvironment.setup()
        pipeline = env.get_pipeline()
        
        # Process audio
        result = pipeline.process(...)
    """
    
    def __init__(
        self,
        content_dir: Path = Path("/content"),
        drive_folder: str = "QuranSegmenter"
    ):
        self.content_dir = Path(content_dir)
        self.drive_folder = drive_folder
        self.data_dir = self.content_dir / "data"
        self.drive_data_dir: Optional[Path] = None
        
        self._storage = None
        self._config = None
        self._pipeline = None
        self._server = None
    
    @classmethod
    def setup(
        cls,
        mount_drive: bool = True,
        drive_folder: str = "QuranSegmenter"
    ) -> "ColabEnvironment":
        """
        Complete Colab environment setup.
        
        Args:
            mount_drive: Whether to mount Google Drive for persistence
            drive_folder: Folder name in Google Drive
            
        Returns:
            Configured ColabEnvironment
        """
        env = cls(drive_folder=drive_folder)
        
        print("=" * 60)
        print("QURAN SEGMENTER - COLAB SETUP")
        print("=" * 60)
        
        # Mount Google Drive
        if mount_drive:
            env._mount_drive()
        
        # Sync from Drive if available
        env._sync_from_drive()
        
        # Initialize configuration
        env._init_config()
        
        # Detect existing assets
        env._config.detect_existing_assets()
        
        # Copy required data files
        env._setup_data_files()
        
        print("\n✓ Environment setup complete!")
        env._config.print_status()
        
        return env
    
    def _mount_drive(self):
        """Mount Google Drive."""
        try:
            from google.colab import drive
            
            drive_mount = Path("/content/drive")
            if not (drive_mount / "MyDrive").exists():
                print("\nMounting Google Drive...")
                drive.mount(str(drive_mount))
            
            self.drive_data_dir = drive_mount / "MyDrive" / self.drive_folder
            self.drive_data_dir.mkdir(parents=True, exist_ok=True)
            print(f"✓ Google Drive mounted at: {self.drive_data_dir}")
            
        except ImportError:
            print("⚠ Not in Colab, skipping Drive mount")
        except Exception as e:
            print(f"⚠ Could not mount Drive: {e}")
    
    def _sync_from_drive(self):
        """Sync data from Google Drive to local."""
        if not self.drive_data_dir or not self.drive_data_dir.exists():
            return
        
        print("\nSyncing from Google Drive...")
        
        # Items to sync
        sync_items = ["config.json", "embeddings", "translations"]
        synced = 0
        
        for item in sync_items:
            src = self.drive_data_dir / item
            dst = self.data_dir / item
            
            if src.exists():
                if src.is_file():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    # Only copy if newer or doesn't exist
                    if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
                        shutil.copy2(src, dst)
                        synced += 1
                elif src.is_dir():
                    dst.mkdir(parents=True, exist_ok=True)
                    for f in src.iterdir():
                        fdst = dst / f.name
                        if not fdst.exists() or f.stat().st_mtime > fdst.stat().st_mtime:
                            if f.is_file():
                                shutil.copy2(f, fdst)
                                synced += 1
        
        if synced > 0:
            print(f"✓ Synced {synced} items from Drive")
    
    def sync_to_drive(self):
        """Sync local data to Google Drive."""
        if not self.drive_data_dir:
            return
        
        print("Syncing to Google Drive...")
        
        sync_items = ["config.json", "embeddings", "translations"]
        
        for item in sync_items:
            src = self.data_dir / item
            dst = self.drive_data_dir / item
            
            if src.exists():
                if src.is_file():
                    shutil.copy2(src, dst)
                elif src.is_dir():
                    dst.mkdir(parents=True, exist_ok=True)
                    for f in src.iterdir():
                        if f.is_file():
                            shutil.copy2(f, dst / f.name)
        
        print("✓ Synced to Drive")
    
    def _init_config(self):
        """Initialize or load configuration."""
        from ..config import Config
        
        self._config = Config.load_or_create(
            data_dir=self.data_dir,
            base_dir=self.content_dir
        )
        
        # Update paths for Colab environment
        self._config.lafzize_dir = self.content_dir / "lafzize"
        self._config.rabtize_dir = self.content_dir / "rabtize"
        self._config.jumlize_binary = self.content_dir / "jumlize"
        self._config.qpc_words_file = self.content_dir / "qpc-hafs-word-by-word.json"
        self._config.quran_metadata_file = self.content_dir / "quran-metadata-misc.json"
        self._config.save()
    
    def _setup_data_files(self):
        """Ensure required data files are in place."""
        # Files that need to be in lafzize directory
        lafzize_files = [
            "qpc-hafs-word-by-word.json",
            "quran-metadata-misc.json"
        ]
        
        for fname in lafzize_files:
            src = self.content_dir / fname
            dst = self._config.lafzize_dir / fname
            
            if src.exists() and not dst.exists():
                shutil.copy(src, dst)
                print(f"  Copied {fname} to lafzize/")
        
        # Files that need to be in rabtize directory  
        rabtize_files = ["qpc-hafs-word-by-word.json"]
        
        for fname in rabtize_files:
            src = self.content_dir / fname
            dst = self._config.rabtize_dir / fname
            
            if src.exists() and not dst.exists():
                shutil.copy(src, dst)
                print(f"  Copied {fname} to rabtize/")
    
    @property
    def config(self):
        """Get configuration."""
        if self._config is None:
            self._init_config()
        return self._config
    
    def reload_config(self):
        """Reload configuration from disk."""
        self._config.reload()
        print("✓ Configuration reloaded")
        self._config.print_status()
    
    def get_pipeline(self):
        """Get or create pipeline instance."""
        if self._pipeline is None:
            from ..pipeline.orchestrator import QuranSegmenterPipeline
            self._pipeline = QuranSegmenterPipeline(self.config)
        return self._pipeline
    
    def start_lafzize_server(self, wait: bool = True, timeout: int = 120) -> bool:
        """Start the lafzize server."""
        from ..utils.server import LafzizeServer
        
        if self._server is None:
            self._server = LafzizeServer(
                lafzize_dir=self._config.lafzize_dir,
                host=self._config.lafzize.server_host,
                port=self._config.lafzize.server_port,
                metadata_file=self._config.quran_metadata_file
            )
        
        success = self._server.start(wait=wait, timeout=timeout)
        
        if success:
            print(f"✓ Lafzize server running at {self._server.base_url}")
        else:
            print("✗ Failed to start lafzize server")
            print("Server log:")
            print(self._server.get_log())
        
        return success
    
    def stop_lafzize_server(self):
        """Stop the lafzize server."""
        if self._server:
            self._server.stop()
            print("✓ Lafzize server stopped")
    
    def register_translation(
        self,
        translation_id: str,
        name: str,
        language_code: str,
        file_path: Optional[str] = None,
        upload: bool = False
    ):
        """
        Register a translation.
        
        Args:
            translation_id: Unique identifier
            name: Display name
            language_code: Language code (e.g., 'en', 'ar')
            file_path: Path to translation file (if already uploaded)
            upload: Whether to upload file interactively
        """
        if upload:
            from google.colab import files
            print("Upload your translation JSON file:")
            uploaded = files.upload()
            
            if not uploaded:
                print("No file uploaded")
                return
            
            filename = list(uploaded.keys())[0]
            file_path = self.content_dir / filename
        
        if not file_path:
            # Check if file already exists
            possible_paths = [
                self.content_dir / f"{translation_id}.json",
                self._config.translations_dir / f"{translation_id}.json",
            ]
            for p in possible_paths:
                if p.exists():
                    file_path = p
                    print(f"Found existing file: {p}")
                    break
        
        if not file_path or not Path(file_path).exists():
            print(f"✗ No translation file found for {translation_id}")
            print("Either specify file_path or set upload=True")
            return
        
        self._config.register_translation(
            translation_id=translation_id,
            name=name,
            language_code=language_code,
            source_file=Path(file_path)
        )
        
        print(f"✓ Registered translation: {translation_id}")
        self.sync_to_drive()
    
    def prepare_translation(
        self,
        translation_id: str,
        api_key: Optional[str] = None,
        skip_segmentation: bool = False,
        force: bool = False
    ):
        """
        Prepare a translation for processing.
        
        Args:
            translation_id: Translation to prepare
            api_key: Gemini API key (if segmentation needed)
            skip_segmentation: Skip if already segmented
            force: Force regeneration
        """
        pipeline = self.get_pipeline()
        
        print(f"\nPreparing translation: {translation_id}")
        print("=" * 50)
        
        status = pipeline.prepare_translation(
            translation_id=translation_id,
            api_key=api_key,
            skip_segmentation=skip_segmentation,
            force=force
        )
        
        print("\nResults:")
        for step, result in status["steps"].items():
            icon = "✓" if "complete" in str(result).lower() or "already" in str(result).lower() else "✗"
            print(f"  {icon} {step}: {result}")
        
        if status.get("ready"):
            print(f"\n✓ Translation '{translation_id}' is ready for processing!")
        
        self.sync_to_drive()
        return status
    
    def process_audio(
        self,
        audio_path: str,
        verses: str,
        translation_id: str,
        output_path: Optional[str] = None,
        upload_audio: bool = False
    ):
        """
        Process audio file to generate timed segments.
        
        Args:
            audio_path: Path to audio file
            verses: Verse specification (e.g., "2:282", "2:1-10", "2")
            translation_id: Translation to use
            output_path: Where to save output
            upload_audio: Whether to upload audio interactively
        """
        if upload_audio:
            from google.colab import files
            print("Upload your audio file (MP3):")
            uploaded = files.upload()
            
            if not uploaded:
                print("No file uploaded")
                return None
            
            audio_path = self.content_dir / list(uploaded.keys())[0]
        
        audio_path = Path(audio_path)
        if not audio_path.exists():
            print(f"✗ Audio file not found: {audio_path}")
            return None
        
        if not output_path:
            output_path = self.content_dir / f"segments_{audio_path.stem}.json"
        
        # Ensure server is running
        if not self.start_lafzize_server():
            return None
        
        pipeline = self.get_pipeline()
        
        print(f"\nProcessing: {audio_path.name}")
        print(f"Verses: {verses}")
        print(f"Translation: {translation_id}")
        print("=" * 50)
        
        try:
            result = pipeline.process(
                audio_path=audio_path,
                verses=verses,
                translation_id=translation_id,
                output_path=Path(output_path)
            )
            
            print(f"\n✓ Processed {len(result.verses)} verses")
            total_segments = sum(len(vs.segments) for vs in result.verses.values())
            print(f"✓ Total segments: {total_segments}")
            
            if result.warnings:
                print(f"\nWarnings ({len(result.warnings)}):")
                for w in result.warnings[:5]:
                    print(f"  - {w}")
            
            print(f"\n✓ Output saved to: {output_path}")
            
            # Show sample
            if result.verses:
                print("\nSample output (first verse, first 2 segments):")
                import json
                first_key = list(result.verses.keys())[0]
                sample = {first_key: result.verses[first_key].to_dict()[:2]}
                print(json.dumps(sample, indent=2, ensure_ascii=False))
            
            return result
            
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def download_result(self, path: str):
        """Download a result file."""
        from google.colab import files
        path = Path(path)
        if path.exists():
            files.download(str(path))
            print(f"✓ Downloading: {path}")
        else:
            print(f"✗ File not found: {path}")
    
    def cleanup(self):
        """Cleanup resources."""
        self.stop_lafzize_server()
        if self._pipeline:
            self._pipeline.cleanup()
        print("✓ Cleanup complete")