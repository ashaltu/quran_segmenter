# quran_segmenter/config.py
"""
Central configuration management with persistence.
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class TranslationConfig:
    """Configuration for a single translation."""
    id: str
    name: str
    language_code: str
    file_path: str  # Store as string for JSON serialization
    is_segmented: bool = False
    segmented_file_path: Optional[str] = None
    embeddings_path: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "language_code": self.language_code,
            "file_path": self.file_path,
            "is_segmented": self.is_segmented,
            "segmented_file_path": self.segmented_file_path,
            "embeddings_path": self.embeddings_path
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TranslationConfig":
        return cls(
            id=data["id"],
            name=data["name"],
            language_code=data["language_code"],
            file_path=data["file_path"],
            is_segmented=data.get("is_segmented", False),
            segmented_file_path=data.get("segmented_file_path"),
            embeddings_path=data.get("embeddings_path")
        )
    
    def get_file_path(self) -> Path:
        return Path(self.file_path)
    
    def get_segmented_path(self) -> Optional[Path]:
        return Path(self.segmented_file_path) if self.segmented_file_path else None
    
    def get_embeddings_path(self) -> Optional[Path]:
        return Path(self.embeddings_path) if self.embeddings_path else None


@dataclass
class LafzizeConfig:
    """Configuration for lafzize audio alignment."""
    server_host: str = "127.0.0.1"
    server_port: int = 8004
    timeout: int = 300
    
    def to_dict(self) -> dict:
        return {"server_host": self.server_host, "server_port": self.server_port, "timeout": self.timeout}
    
    @classmethod
    def from_dict(cls, data: dict) -> "LafzizeConfig":
        return cls(**data)


@dataclass
class JumlizeConfig:
    """Configuration for jumlize LLM segmentation."""
    model: str = "gemini-2.5-flash"
    thinking_budget: int = 0
    temperature: float = 0.0
    max_retries: int = 5
    
    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "thinking_budget": self.thinking_budget,
            "temperature": self.temperature,
            "max_retries": self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "JumlizeConfig":
        return cls(**{k: v for k, v in data.items() if k in ['model', 'thinking_budget', 'temperature', 'max_retries']})


@dataclass 
class RabtizeConfig:
    """Configuration for rabtize alignment."""
    embedding_model: str = "intfloat/multilingual-e5-large"
    device: str = "cuda"
    batch_size: int = 512
    
    def to_dict(self) -> dict:
        return {"embedding_model": self.embedding_model, "device": self.device, "batch_size": self.batch_size}
    
    @classmethod
    def from_dict(cls, data: dict) -> "RabtizeConfig":
        return cls(**data)


class Config:
    """
    Main configuration container with persistence.
    
    Usage:
        # Create new or load existing
        config = Config.load_or_create(data_dir)
        
        # Make changes
        config.register_translation(...)
        
        # Changes auto-save, or manually:
        config.save()
        
        # Reload from disk
        config.reload()
    """
    
    def __init__(
        self,
        data_dir: Path,
        base_dir: Optional[Path] = None,
        storage_manager=None
    ):
        self.data_dir = Path(data_dir)
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self._storage = storage_manager
        
        # Derived paths
        self.translations_dir = self.data_dir / "translations"
        self.embeddings_dir = self.data_dir / "embeddings"
        self.cache_dir = self.data_dir / "cache"
        self.config_path = self.data_dir / "config.json"
        
        # External tools (set these based on environment)
        self.lafzize_dir: Path = self.base_dir / "lafzize"
        self.rabtize_dir: Path = self.base_dir / "rabtize"
        self.jumlize_binary: Path = self.base_dir / "jumlize"
        self.qpc_words_file: Path = self.base_dir / "qpc-hafs-word-by-word.json"
        self.quran_metadata_file: Path = self.base_dir / "quran-metadata-misc.json"
        
        # Component configs
        self.lafzize = LafzizeConfig()
        self.jumlize = JumlizeConfig()
        self.rabtize = RabtizeConfig()
        
        # State
        self.translations: Dict[str, TranslationConfig] = {}
        self.spans_embeddings_generated: bool = False
        self._spans_embeddings_path = None
        
        # Create directories
        for d in [self.translations_dir, self.embeddings_dir, self.cache_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    @property
    def spans_embeddings_path(self) -> Path:
        return self.embeddings_dir / "spans.npz"
    
    @spans_embeddings_path.setter
    def spans_embeddings_path(self, value: Path):
        self._spans_embeddings_path = Path(value)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "data_dir": str(self.data_dir),
            "base_dir": str(self.base_dir),
            "lafzize_dir": str(self.lafzize_dir),
            "rabtize_dir": str(self.rabtize_dir),
            "jumlize_binary": str(self.jumlize_binary),
            "qpc_words_file": str(self.qpc_words_file),
            "quran_metadata_file": str(self.quran_metadata_file),
            "lafzize": self.lafzize.to_dict(),
            "jumlize": self.jumlize.to_dict(),
            "rabtize": self.rabtize.to_dict(),
            "translations": {k: v.to_dict() for k, v in self.translations.items()},
            "spans_embeddings_generated": self.spans_embeddings_generated,
            "spans_embeddings_path": str(self.spans_embeddings_path)
        }
    
    def _update_from_dict(self, data: dict):
        """Update config from dictionary."""
        if "lafzize_dir" in data:
            self.lafzize_dir = Path(data["lafzize_dir"])
        if "rabtize_dir" in data:
            self.rabtize_dir = Path(data["rabtize_dir"])
        if "jumlize_binary" in data:
            self.jumlize_binary = Path(data["jumlize_binary"])
        if "qpc_words_file" in data:
            self.qpc_words_file = Path(data["qpc_words_file"])
        if "quran_metadata_file" in data:
            self.quran_metadata_file = Path(data["quran_metadata_file"])
        
        if "lafzize" in data:
            self.lafzize = LafzizeConfig.from_dict(data["lafzize"])
        if "jumlize" in data:
            self.jumlize = JumlizeConfig.from_dict(data["jumlize"])
        if "rabtize" in data:
            self.rabtize = RabtizeConfig.from_dict(data["rabtize"])
        
        self.translations = {}
        for tid, tdata in data.get("translations", {}).items():
            self.translations[tid] = TranslationConfig.from_dict(tdata)
        
        self.spans_embeddings_generated = data.get("spans_embeddings_generated", False)
        
        # Also check if file actually exists
        if self.spans_embeddings_path.exists():
            self.spans_embeddings_generated = True
    
    def save(self):
        """Save configuration to disk."""
        data = self.to_dict()
        
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        if self._storage:
            self._storage.sync_to_drive(["config.json"])
        
        logger.debug(f"Config saved to {self.config_path}")
    
    def reload(self):
        """Reload configuration from disk."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._update_from_dict(data)
            logger.info(f"Config reloaded from {self.config_path}")
        else:
            logger.warning(f"No config file at {self.config_path}")
    
    @classmethod
    def load_or_create(
        cls,
        data_dir: Path,
        base_dir: Optional[Path] = None,
        storage_manager=None
    ) -> "Config":
        """
        Load existing config or create new one.
        Does NOT overwrite existing config.
        """
        data_dir = Path(data_dir)
        # Allow callers to pass either a data directory or a full config path
        if data_dir.suffix == ".json":
            data_dir = data_dir.parent
        config_path = data_dir / "config.json"
        
        config = cls(
            data_dir=data_dir,
            base_dir=base_dir,
            storage_manager=storage_manager
        )
        
        if config_path.exists():
            logger.info(f"Loading existing config from {config_path}")
            config.reload()
        else:
            logger.info(f"Creating new config at {config_path}")
            config.save()
        
        return config
    
    def register_translation(
        self,
        translation_id: str,
        name: str,
        language_code: str,
        source_file: Path,
        copy_to_data_dir: bool = True,
        spans_embeddings_filepath: Optional[Path] = None,
        segment_embeddings_filepath: Optional[Path] = None
    ) -> TranslationConfig:
        """Register a new translation."""
        source_file = Path(source_file)
        
        if not source_file.exists():
            raise FileNotFoundError(f"Translation file not found: {source_file}")
        
        if copy_to_data_dir:
            dest = self.translations_dir / f"{translation_id}.json"
            if not dest.exists():
                import shutil
                shutil.copy(source_file, dest)
                logger.info(f"Copied translation to {dest}")
            file_path = str(dest)
        else:
            file_path = str(source_file)
        
        tc = TranslationConfig(
            id=translation_id,
            name=name,
            language_code=language_code,
            file_path=file_path,
        )
        
        # Check if already segmented (file has segments)
        self._check_segmentation_status(tc)
        
        # Check if embeddings exist
        emb_path = self.embeddings_dir / f"{translation_id}.npz"
        if emb_path.exists():
            tc.embeddings_path = str(emb_path)

        # If provided, set embeddings paths
        if segment_embeddings_filepath:
            tc.embeddings_path = str(segment_embeddings_filepath)

        # If provided, set spans embeddings (one-time) for the config
        if spans_embeddings_filepath and spans_embeddings_filepath.exists():
            self.spans_embeddings_generated = True
            self.spans_embeddings_path = spans_embeddings_filepath
        
        self.translations[translation_id] = tc
        self.save()
        
        logger.info(f"Registered translation: {translation_id}")
        return tc
    
    def _check_segmentation_status(self, tc: TranslationConfig):
        """Check if translation file already has segments."""
        try:
            with open(tc.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check first few verses for segments
            sample_keys = list(data.keys())[:10]
            has_segments = all("segments" in data[k] for k in sample_keys if k in data)
            
            if has_segments:
                tc.is_segmented = True
                tc.segmented_file_path = tc.file_path
                logger.info(f"Translation {tc.id} appears to be pre-segmented")
        except Exception as e:
            logger.debug(f"Could not check segmentation status: {e}")
    
    def get_translation(self, translation_id: str) -> TranslationConfig:
        """Get translation config by ID."""
        if translation_id not in self.translations:
            available = list(self.translations.keys())
            raise ValueError(
                f"Translation '{translation_id}' not found. "
                f"Available: {available}. "
                f"Use 'register' command to add it."
            )
        return self.translations[translation_id]
    
    def update_translation(
        self,
        translation_id: str,
        is_segmented: bool = None,
        segmented_file_path: Path = None,
        embeddings_path: Path = None
    ):
        """Update translation status."""
        tc = self.get_translation(translation_id)
        
        if is_segmented is not None:
            tc.is_segmented = is_segmented
        if segmented_file_path is not None:
            tc.segmented_file_path = str(segmented_file_path)
        if embeddings_path is not None:
            tc.embeddings_path = str(embeddings_path)
        
        self.save()
    
    def detect_existing_assets(self):
        """Scan for existing assets and update config."""
        updated = False
        
        # Check spans embeddings
        if self.spans_embeddings_path and self.spans_embeddings_path.exists() and not self.spans_embeddings_generated:
            self.spans_embeddings_generated = True
            updated = True
            logger.info("Found existing spans embeddings")
        
        # Check translation embeddings
        for emb_file in self.embeddings_dir.glob("*.npz"):
            if emb_file.name == "spans.npz":
                continue
            
            tid = emb_file.stem
            if tid in self.translations:
                tc = self.translations[tid]
                if not tc.embeddings_path:
                    tc.embeddings_path = str(emb_file)
                    updated = True
                    logger.info(f"Found existing embeddings for {tid}")
        
        if updated:
            self.save()
    
    def print_status(self):
        """Print current configuration status."""
        print("\n" + "=" * 60)
        print("QURAN SEGMENTER STATUS")
        print("=" * 60)
        print(f"Data directory: {self.data_dir}")
        print(f"Spans embeddings: {'✓ Generated' if self.spans_embeddings_generated else '✗ Not generated'}")
        print(f"\nRegistered Translations ({len(self.translations)}):")
        
        if not self.translations:
            print("  (none)")
        else:
            for tid, tc in self.translations.items():
                seg_status = "✓" if tc.is_segmented else "✗"
                emb_status = "✓" if tc.embeddings_path and Path(tc.embeddings_path).exists() else "✗"
                ready = tc.is_segmented and tc.embeddings_path and self.spans_embeddings_generated
                ready_status = "✓ READY" if ready else "✗ Not ready"
                print(f"  {tid}:")
                print(f"    Language: {tc.language_code}")
                print(f"    Segmented: {seg_status}  Embeddings: {emb_status}")
                print(f"    Status: {ready_status}")
        print("=" * 60 + "\n")

def get_config() -> Config:
    """
    Get the global configuration instance.
    
    QURAN_SEGMENTER_CONFIG should point directly to the config JSON file.
    """
    env_path = os.environ.get("QURAN_SEGMENTER_CONFIG")
    config_path = Path(env_path).expanduser() if env_path else Path("./quran_data/config.json")
    return Config.load_or_create(config_path)
