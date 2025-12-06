# quran_segmenter/utils/server.py
"""
Server management utilities for lafzize.
"""
import subprocess
import time
import requests
import signal
import atexit
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ServerManager:
    """Manages the lafzize FastAPI server lifecycle."""
    
    def __init__(
        self,
        lafzize_dir: Path,
        host: str = "127.0.0.1",
        port: int = 8004,
        log_file: Optional[Path] = None
    ):
        self.lafzize_dir = lafzize_dir
        self.host = host
        self.port = port
        self.log_file = log_file or Path("/tmp/lafzize_server.log")
        self._process: Optional[subprocess.Popen] = None
        self._started_by_us = False
        
        # Register cleanup on exit
        atexit.register(self.stop)
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    def is_running(self) -> bool:
        """Check if server is responding."""
        try:
            response = requests.get(f"{self.base_url}/", timeout=2)
            # lafzize doesn't have /health, root returns 405 for GET but server is up
            return response.status_code in [200, 405, 422]
        except requests.exceptions.RequestException:
            return False
    
    def wait_for_ready(self, timeout: int = 60) -> bool:
        """Wait for server to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_running():
                return True
            time.sleep(1)
        return False
    
    def start(self, wait: bool = True, timeout: int = 60) -> bool:
        """Start the lafzize server if not running."""
        if self.is_running():
            logger.info("Lafzize server already running")
            return True
        
        # Kill any zombie process on our port
        self._kill_port()
        
        logger.info(f"Starting lafzize server on port {self.port}...")
        
        log_handle = open(self.log_file, "w")
        
        self._process = subprocess.Popen(
            ["fastapi", "run", "--port", str(self.port)],
            cwd=str(self.lafzize_dir),
            stdout=log_handle,
            stderr=log_handle
        )
        self._started_by_us = True
        
        if wait:
            if self.wait_for_ready(timeout):
                logger.info("Lafzize server started successfully")
                return True
            else:
                logger.error("Lafzize server failed to start")
                self.stop()
                return False
        
        return True
    
    def stop(self):
        """Stop the server if we started it."""
        if self._process and self._started_by_us:
            logger.info("Stopping lafzize server...")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
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
                    try:
                        subprocess.run(["kill", "-9", pid], check=False)
                    except:
                        pass
                time.sleep(1)
        except FileNotFoundError:
            pass  # lsof not available
    
    def ensure_running(self) -> bool:
        """Ensure server is running, starting if necessary."""
        if self.is_running():
            return True
        return self.start()