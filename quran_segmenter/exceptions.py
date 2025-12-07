# quran_segmenter/exceptions.py
"""
Custom exceptions for the pipeline.
"""


class QuranSegmenterError(Exception):
    """Base exception for quran segmenter."""
    pass


class ConfigurationError(QuranSegmenterError):
    """Configuration-related errors."""
    pass


class LafzizeError(QuranSegmenterError):
    """Errors from lafzize processing."""
    pass


class JumlizeError(QuranSegmenterError):
    """Errors from jumlize processing."""
    pass


class RabtizeError(QuranSegmenterError):
    """Errors from rabtize processing."""
    pass


class TranslationNotPreparedError(QuranSegmenterError):
    """Translation hasn't been prepared (segmented/embedded)."""
    def __init__(self, translation_id: str, missing: str):
        self.translation_id = translation_id
        self.missing = missing
        super().__init__(
            f"Translation '{translation_id}' not prepared: missing {missing}. "
            f"Run 'quran-segmenter prepare {translation_id}' first."
        )


class ServerNotRunningError(QuranSegmenterError):
    """Required server is not running."""
    pass


class CacheError(QuranSegmenterError):
    """Cache-related errors."""
    pass