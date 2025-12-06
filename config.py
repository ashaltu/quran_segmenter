# quran_segmenter/config.py
"""
Central configuration management with environment-aware defaults.
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


@dataclass
class TranslationConfig:
    """Configuration for a single translation."""
    id: str
    name: str
    language_code: str
    file_path: Path
    is_segmented: bool = False
    segmented_file_path: Optional[Path] = None
    embeddings_path: Optional[Path] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "language_code": self.language_code,
            "file_path": str(self.file_path),
            "is_segmented": self.is_segmented,
            "segmented_file_path": str(self.segmented_file_path) if self.segmented_file_path else None,
            "embeddings_path": str(self.embeddings_path) if self.embeddings_path else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TranslationConfig":
        return cls(
            id=data["id"],
            name=data["name"],
            language_code=data["language_code"],
            file_path=Path(data["file_path"]),
            is_segmented=data.get("is_segmented", False),
            segmented_file_path=Path(data["segmented_file_path"]) if data.get("segmented_file_path") else None,
            embeddings_path=Path(data["embeddings_path"]) if data.get("embeddings_path") else None
        )


@dataclass
class JumlizeConfig:
    """Configuration for jumlize LLM segmentation."""
    api_key: Optional[str] = None
    model: str = "gemini-2.5-flash"
    thinking_budget: int = 0
    temperature: float = 0.0
    max_retries: int = 3
    retry_escalation: List[dict] = field(default_factory=lambda: [
        {"model": "gemini-2.5-flash", "thinking_budget": 0},
        {"model": "gemini-2.5-flash", "thinking_budget": 1000},
        {"model": "gemini-2.5-flash", "thinking_budget": 2000},
        {"model": "gemini-2.5-pro", "thinking_level": "LOW"},
        {"model": "gemini-2.5-pro", "thinking_level": "HIGH"},
    ])


@dataclass
class RabtizeConfig:
    """Configuration for rabtize alignment."""
    embedding_model: str = "intfloat/multilingual-e5-large"
    device: str = "cuda"
    batch_size: int = 512


@dataclass
class LafzizeConfig:
    """Configuration for lafzize audio alignment."""
    server_host: str = "127.0.0.1"
    server_port: int = 8004
    timeout: int = 300  # seconds


@dataclass
class Config:
    """Main configuration container."""
    # Base paths
    base_dir: Path = field(default_factory=lambda: Path.cwd())
    data_dir: Path = field(default_factory=lambda: Path.cwd() / "data")
    
    # Sub-directories (will be created under data_dir)
    translations_dir: Path = field(init=False)
    embeddings_dir: Path = field(init=False)
    timestamps_dir: Path = field(init=False)
    cache_dir: Path = field(init=False)
    
    # External tool paths
    lafzize_dir: Path = field(default_factory=lambda: Path.cwd() / "lafzize")
    rabtize_dir: Path = field(default_factory=lambda: Path.cwd() / "rabtize")
    jumlize_binary: Path = field(default_factory=lambda: Path.cwd() / "jumlize")
    
    # Data files
    qpc_words_file: Path = field(default_factory=lambda: Path.cwd() / "qpc-hafs-word-by-word.json")
    quran_metadata_file: Path = field(default_factory=lambda: Path.cwd() / "quran-metadata-ayah.json")
    
    # Component configs
    lafzize: LafzizeConfig = field(default_factory=LafzizeConfig)
    jumlize: JumlizeConfig = field(default_factory=JumlizeConfig)
    rabtize: RabtizeConfig = field(default_factory=RabtizeConfig)
    
    # Translation registry
    translations: Dict[str, TranslationConfig] = field(default_factory=dict)
    
    # State tracking
    spans_embeddings_generated: bool = False
    spans_embeddings_path: Optional[Path] = None
    
    def __post_init__(self):
        self.translations_dir = self.data_dir / "translations"
        self.embeddings_dir = self.data_dir / "embeddings"
        self.timestamps_dir = self.data_dir / "timestamps"
        self.cache_dir = self.data_dir / "cache"
        
        # Create directories
        for dir_path in [self.translations_dir, self.embeddings_dir, 
                         self.timestamps_dir, self.cache_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Set spans embeddings path
        self.spans_embeddings_path = self.embeddings_dir / "spans.npz"
        self.spans_embeddings_generated = self.spans_embeddings_path.exists()
    
    def save(self, path: Optional[Path] = None):
        """Save configuration to JSON file."""
        path = path or (self.data_dir / "config.json")
        data = {
            "base_dir": str(self.base_dir),
            "data_dir": str(self.data_dir),
            "lafzize_dir": str(self.lafzize_dir),
            "rabtize_dir": str(self.rabtize_dir),
            "jumlize_binary": str(self.jumlize_binary),
            "qpc_words_file": str(self.qpc_words_file),
            "quran_metadata_file": str(self.quran_metadata_file),
            "spans_embeddings_generated": self.spans_embeddings_generated,
            "translations": {k: v.to_dict() for k, v in self.translations.items()},
            "lafzize": {
                "server_host": self.lafzize.server_host,
                "server_port": self.lafzize.server_port,
                "timeout": self.lafzize.timeout
            },
            "jumlize": {
                "model": self.jumlize.model,
                "thinking_budget": self.jumlize.thinking_budget,
                "temperature": self.jumlize.temperature,
                "max_retries": self.jumlize.max_retries,
                "retry_escalation": self.jumlize.retry_escalation
            },
            "rabtize": {
                "embedding_model": self.rabtize.embedding_model,
                "device": self.rabtize.device,
                "batch_size": self.rabtize.batch_size
            }
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Configuration saved to {path}")
    
    @classmethod
    def load(cls, path: Path) -> "Config":
        """Load configuration from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        config = cls(
            base_dir=Path(data.get("base_dir", ".")),
            data_dir=Path(data.get("data_dir", "./data")),
            lafzize_dir=Path(data.get("lafzize_dir", "./lafzize")),
            rabtize_dir=Path(data.get("rabtize_dir", "./rabtize")),
            jumlize_binary=Path(data.get("jumlize_binary", "./jumlize")),
            qpc_words_file=Path(data.get("qpc_words_file", "./qpc-hafs-word-by-word.json")),
            quran_metadata_file=Path(data.get("quran_metadata_file", "./quran-metadata-ayah.json")),
        )
        
        config.spans_embeddings_generated = data.get("spans_embeddings_generated", False)
        
        # Load component configs
        if "lafzize" in data:
            config.lafzize = LafzizeConfig(**data["lafzize"])
        if "jumlize" in data:
            jdata = data["jumlize"]
            config.jumlize = JumlizeConfig(
                model=jdata.get("model", "gemini-2.5-flash"),
                thinking_budget=jdata.get("thinking_budget", 0),
                temperature=jdata.get("temperature", 0.0),
                max_retries=jdata.get("max_retries", 3),
                retry_escalation=jdata.get("retry_escalation", [])
            )
        if "rabtize" in data:
            config.rabtize = RabtizeConfig(**data["rabtize"])
        
        # Load translations
        for tid, tdata in data.get("translations", {}).items():
            config.translations[tid] = TranslationConfig.from_dict(tdata)
        
        return config
    
    @classmethod
    def load_or_create(cls, path: Optional[Path] = None) -> "Config":
        """Load existing config or create new one."""
        path = path or Path("./data/config.json")
        if path.exists():
            return cls.load(path)
        config = cls()
        config.save(path)
        return config
    
    def register_translation(
        self,
        translation_id: str,
        name: str,
        language_code: str,
        source_file: Path,
        copy_to_data_dir: bool = True
    ) -> TranslationConfig:
        """Register a new translation."""
        if copy_to_data_dir:
            dest = self.translations_dir / f"{translation_id}.json"
            if not dest.exists():
                import shutil
                shutil.copy(source_file, dest)
            file_path = dest
        else:
            file_path = source_file
        
        tc = TranslationConfig(
            id=translation_id,
            name=name,
            language_code=language_code,
            file_path=file_path
        )
        self.translations[translation_id] = tc
        self.save()
        logger.info(f"Registered translation: {translation_id}")
        return tc
    
    def get_translation(self, translation_id: str) -> TranslationConfig:
        """Get translation config, raising error if not found."""
        if translation_id not in self.translations:
            raise ValueError(f"Translation '{translation_id}' not registered. "
                           f"Available: {list(self.translations.keys())}")
        return self.translations[translation_id]
    
    def update_translation_status(
        self,
        translation_id: str,
        is_segmented: bool = None,
        segmented_file_path: Path = None,
        embeddings_path: Path = None
    ):
        """Update translation status after processing."""
        tc = self.get_translation(translation_id)
        if is_segmented is not None:
            tc.is_segmented = is_segmented
        if segmented_file_path is not None:
            tc.segmented_file_path = segmented_file_path
        if embeddings_path is not None:
            tc.embeddings_path = embeddings_path
        self.save()


def get_config() -> Config:
    """Get the global configuration instance."""
    config_path = Path(os.environ.get("QURAN_SEGMENTER_CONFIG", "./data/config.json"))
    return Config.load_or_create(config_path)