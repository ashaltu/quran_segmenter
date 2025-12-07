# quran_segmenter/utils/server.py
"""
Server management utilities for lafzize.
"""
import subprocess
import time
import requests
import atexit
from pathlib import Path
from typing import Optional
import logging
import shutil

logger = logging.getLogger(__name__)


class LafzizeServer:
    """Manages the lafzize FastAPI server lifecycle."""
    
    def __init__(
        self,
        lafzize_dir: Path,
        host: str = "127.0.0.1",
        port: int = 8004,
        metadata_file: Optional[Path] = None
    ):
        self.lafzize_dir = Path(lafzize_dir)
        self.host = host
        self.port = port
        self.metadata_file = metadata_file
        self._process: Optional[subprocess.Popen] = None
        self._started_by_us = False
        self._log_file: Optional[Path] = None
        
        atexit.register(self.stop)
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    def _ensure_metadata(self):
        """Ensure metadata file is in lafzize directory."""
        if not self.metadata_file:
            return
        
        dest = self.lafzize_dir / "quran-metadata-misc.json"
        if not dest.exists() and self.metadata_file.exists():
            shutil.copy(self.metadata_file, dest)
            logger.info(f"Copied metadata to {dest}")
    
    def is_running(self) -> bool:
        """Check if server is running and responsive."""
        try:
            # Try POST to root (lafzize expects POST with files)
            # A 422 means server is up but missing required fields
            response = requests.post(
                self.base_url,
                timeout=5,
                data={}
            )
            return response.status_code in [200, 422]
        except requests.exceptions.RequestException:
            return False
    
    def wait_for_ready(self, timeout: int = 120) -> bool:
        """Wait for server to be ready."""
        start = time.time()
        logger.info("Waiting for lafzize server to be ready...")
        
        while time.time() - start < timeout:
            if self.is_running():
                logger.info("✓ Lafzize server is ready")
                return True
            time.sleep(2)
            
            # Check if process died
            if self._process and self._process.poll() is not None:
                logger.error("Lafzize server process died")
                if self._log_file and self._log_file.exists():
                    print(f"Server log ({self._log_file}):")
                    print(self._log_file.read_text()[-2000:])
                return False
        
        logger.error(f"Lafzize server not ready after {timeout}s")
        return False
    
    def start(self, wait: bool = True, timeout: int = 120) -> bool:
        """Start the lafzize server if not running."""
        if self.is_running():
            logger.info("Lafzize server already running")
            return True
        
        # Ensure metadata file is present
        self._ensure_metadata()
        
        # Also ensure qpc words file is present
        qpc_src = self.lafzize_dir.parent / "qpc-hafs-word-by-word.json"
        qpc_dst = self.lafzize_dir / "qpc-hafs-word-by-word.json"
        if qpc_src.exists() and not qpc_dst.exists():
            shutil.copy(qpc_src, qpc_dst)
        
        # Kill any zombie process on our port
        self._kill_port()
        time.sleep(1)
        
        logger.info(f"Starting lafzize server on port {self.port}...")
        
        self._log_file = Path("/tmp/lafzize_server.log")
        log_handle = open(self._log_file, "w")
        
        self._process = subprocess.Popen(
            ["fastapi", "run", "--port", str(self.port)],
            cwd=str(self.lafzize_dir),
            stdout=log_handle,
            stderr=log_handle
        )
        self._started_by_us = True
        
        if wait:
            return self.wait_for_ready(timeout)
        return True
    
    def stop(self):
        """Stop the server if we started it."""
        if self._process and self._started_by_us:
            logger.info("Stopping lafzize server...")
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None
            self._started_by_us = False
    
    def _kill_port(self):
        """Kill any process using our port."""
        try:
            result = subprocess.run(
                ["lsof", "-t", "-i", f":{self.port}"],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split("\n")
                for pid in pids:
                    subprocess.run(["kill", "-9", pid], check=False)
                logger.debug(f"Killed processes on port {self.port}: {pids}")
        except FileNotFoundError:
            # lsof not available, try fuser
            try:
                subprocess.run(
                    ["fuser", "-k", f"{self.port}/tcp"],
                    capture_output=True,
                    check=False
                )
            except FileNotFoundError:
                pass
    
    def get_log(self, last_n_chars: int = 5000) -> str:
        """Get recent server log content."""
        if self._log_file and self._log_file.exists():
            content = self._log_file.read_text()
            return content[-last_n_chars:] if len(content) > last_n_chars else content
        return ""