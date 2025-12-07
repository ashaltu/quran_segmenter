# quran_segmenter/utils/storage.py
"""
Storage utilities with Google Drive integration for Colab.
"""
import os
import shutil
import json
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages persistent storage with optional Google Drive backing.
    
    In Colab: Uses Google Drive for persistence across sessions.
    Locally: Uses standard filesystem.
    """
    
    def __init__(
        self,
        local_base: Path,
        drive_base: Optional[Path] = None,
        auto_sync: bool = True
    ):
        self.local_base = Path(local_base)
        self.drive_base = Path(drive_base) if drive_base else None
        self.auto_sync = auto_sync
        self._is_colab = self._detect_colab()
        
        # Create local directories
        self.local_base.mkdir(parents=True, exist_ok=True)
    
    def _detect_colab(self) -> bool:
        """Detect if running in Google Colab."""
        try:
            import google.colab
            return True
        except ImportError:
            return False
    
    @classmethod
    def setup_colab(
        cls,
        drive_folder: str = "QuranSegmenter",
        local_base: str = "/content/data"
    ) -> "StorageManager":
        """
        Setup storage for Colab with Google Drive mounting.
        
        Args:
            drive_folder: Folder name within Google Drive
            local_base: Local working directory
            
        Returns:
            Configured StorageManager
        """
        try:
            from google.colab import drive
            
            # Mount Google Drive
            drive_mount = Path("/content/drive")
            if not drive_mount.exists():
                print("Mounting Google Drive...")
                drive.mount(str(drive_mount))
                print("✓ Google Drive mounted")
            
            drive_base = drive_mount / "MyDrive" / drive_folder
            drive_base.mkdir(parents=True, exist_ok=True)
            
            local_path = Path(local_base)
            
            manager = cls(
                local_base=local_path,
                drive_base=drive_base,
                auto_sync=True
            )
            
            # Sync from Drive to local on startup
            manager.sync_from_drive()
            
            return manager
            
        except ImportError:
            logger.warning("Not in Colab, using local storage only")
            return cls(local_base=Path(local_base))
    
    def sync_from_drive(self):
        """Sync data from Google Drive to local."""
        if not self.drive_base or not self.drive_base.exists():
            return
        
        logger.info(f"Syncing from Google Drive: {self.drive_base}")
        
        # Sync specific important files/folders
        sync_items = [
            "config.json",
            "embeddings",
            "translations",
        ]
        
        for item in sync_items:
            src = self.drive_base / item
            dst = self.local_base / item
            
            if src.exists():
                if src.is_file():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    logger.debug(f"  Synced file: {item}")
                elif src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                    logger.debug(f"  Synced folder: {item}")
        
        logger.info("✓ Sync from Drive complete")
    
    def sync_to_drive(self, items: Optional[list] = None):
        """Sync data from local to Google Drive."""
        if not self.drive_base:
            return
        
        items = items or ["config.json", "embeddings", "translations"]
        
        logger.debug(f"Syncing to Google Drive: {items}")
        
        for item in items:
            src = self.local_base / item
            dst = self.drive_base / item
            
            if src.exists():
                if src.is_file():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                elif src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
    
    def save_config(self, config_data: dict):
        """Save configuration with Drive backup."""
        config_path = self.local_base / "config.json"
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        if self.auto_sync and self.drive_base:
            self.sync_to_drive(["config.json"])
    
    def load_config(self) -> Optional[dict]:
        """Load configuration, preferring Drive version if newer."""
        local_path = self.local_base / "config.json"
        drive_path = self.drive_base / "config.json" if self.drive_base else None
        
        # Check which is newer
        local_exists = local_path.exists()
        drive_exists = drive_path and drive_path.exists()
        
        if drive_exists and local_exists:
            # Use newer one
            if drive_path.stat().st_mtime > local_path.stat().st_mtime:
                shutil.copy2(drive_path, local_path)
        elif drive_exists and not local_exists:
            shutil.copy2(drive_path, local_path)
        
        if local_path.exists():
            with open(local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return None
    
    def save_embeddings(self, name: str, data_path: Path):
        """Save embeddings file with Drive backup."""
        embeddings_dir = self.local_base / "embeddings"
        embeddings_dir.mkdir(parents=True, exist_ok=True)
        
        dest = embeddings_dir / name
        if data_path != dest:
            shutil.copy2(data_path, dest)
        
        if self.auto_sync and self.drive_base:
            self.sync_to_drive(["embeddings"])
    
    def get_embeddings_path(self, name: str) -> Path:
        """Get path to embeddings file."""
        return self.local_base / "embeddings" / name
    
    def file_exists(self, relative_path: str) -> bool:
        """Check if file exists in storage."""
        return (self.local_base / relative_path).exists()


def get_storage_manager(
    local_base: str = "./data",
    use_drive: bool = True
) -> StorageManager:
    """
    Get appropriate storage manager for current environment.
    
    Args:
        local_base: Local storage directory
        use_drive: Whether to use Google Drive in Colab
        
    Returns:
        Configured StorageManager
    """
    try:
        import google.colab
        if use_drive:
            return StorageManager.setup_colab(local_base=local_base)
    except ImportError:
        pass
    
    return StorageManager(local_base=Path(local_base))