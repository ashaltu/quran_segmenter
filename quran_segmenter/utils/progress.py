# quran_segmenter/utils/progress.py
"""
Progress reporting utilities.
"""
import sys
import time
from typing import Optional, Callable
from contextlib import contextmanager


class ProgressReporter:
    """Simple progress reporter that works in both CLI and notebooks."""
    
    def __init__(self, total: int, desc: str = "", unit: str = "items"):
        self.total = total
        self.current = 0
        self.desc = desc
        self.unit = unit
        self.start_time = time.time()
        self._last_print = 0
        self._is_notebook = self._detect_notebook()
    
    def _detect_notebook(self) -> bool:
        """Detect if running in Jupyter/Colab."""
        try:
            from IPython import get_ipython
            shell = get_ipython().__class__.__name__
            return shell in ['ZMQInteractiveShell', 'Shell']
        except:
            return False
    
    def update(self, n: int = 1):
        """Update progress by n items."""
        self.current += n
        
        # Rate limit output
        now = time.time()
        if now - self._last_print < 0.5 and self.current < self.total:
            return
        self._last_print = now
        
        self._print_progress()
    
    def _print_progress(self):
        """Print current progress."""
        pct = 100 * self.current / self.total if self.total > 0 else 0
        elapsed = time.time() - self.start_time
        
        if self.current > 0:
            eta = elapsed * (self.total - self.current) / self.current
            eta_str = f"ETA: {eta:.0f}s"
        else:
            eta_str = "ETA: --"
        
        bar_width = 30
        filled = int(bar_width * self.current / self.total) if self.total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        
        line = f"\r{self.desc}: |{bar}| {self.current}/{self.total} {self.unit} ({pct:.1f}%) {eta_str}"
        
        if self._is_notebook:
            from IPython.display import clear_output
            clear_output(wait=True)
            print(line)
        else:
            sys.stdout.write(line)
            sys.stdout.flush()
    
    def finish(self):
        """Mark as complete."""
        self.current = self.total
        self._print_progress()
        print()  # New line
        elapsed = time.time() - self.start_time
        print(f"  Completed in {elapsed:.1f}s")


@contextmanager
def progress_context(total: int, desc: str = "", unit: str = "items"):
    """Context manager for progress reporting."""
    reporter = ProgressReporter(total, desc, unit)
    try:
        yield reporter
    finally:
        reporter.finish()


def wrap_iterable(iterable, desc: str = "", unit: str = "items"):
    """Wrap an iterable with progress reporting."""
    items = list(iterable)
    total = len(items)
    reporter = ProgressReporter(total, desc, unit)
    
    for item in items:
        yield item
        reporter.update()
    
    reporter.finish()