# quran_segmenter/colab_setup.py
"""
Utilities for one-shot Colab setup (installs rabtize, lafzize, jumlize, and wires env vars).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, Optional

from .config import Config
from .exceptions import QuranSegmenterError

LOG_PREFIX = "[setup-colab]"


def _run(cmd, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None):
    """Run a shell command with basic logging."""
    printable_cmd = " ".join(cmd)
    print(f"{LOG_PREFIX} {printable_cmd}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=True)


def _clone_repo(url: str, dest: Path):
    """Clone a repository if the destination does not already exist."""
    if dest.exists():
        print(f"{LOG_PREFIX} Repo already present: {dest}")
        return
    _run(["git", "clone", "-q", url, str(dest)])


def _patch_rabtize_pyproject(pyproject: Path):
    """Relax rabtize Python requirement for Colab (>=3.10)."""
    if not pyproject.exists():
        return
    text = pyproject.read_text()
    if ">=3.13" in text:
        patched = text.replace(">=3.13", ">=3.10")
        pyproject.write_text(patched)
        print(f"{LOG_PREFIX} Patched rabtize Python version to >=3.10")


def _pip_install(args):
    """Install via pip with logging."""
    _run([sys.executable, "-m", "pip"] + args)


def _ensure_go(go_url: str) -> Path:
    """Install Go toolchain if missing, return go binary path."""
    go_bin = Path("/usr/local/go/bin/go")
    if go_bin.exists():
        print(f"{LOG_PREFIX} Go already present: {go_bin}")
        return go_bin
    
    tmp_dir = Path(tempfile.mkdtemp())
    tar_path = tmp_dir / "go.tar.gz"
    print(f"{LOG_PREFIX} Downloading Go from {go_url}")
    urllib.request.urlretrieve(go_url, tar_path)
    _run(["tar", "-C", "/usr/local", "-xzf", str(tar_path)])
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return go_bin


def _install_jumlize(go_bin: Path, jumlize_ref: str, symlink_path: Path) -> Path:
    """Install jumlize via go install and expose it at a stable path."""
    env = os.environ.copy()
    env["PATH"] = f"{go_bin.parent}:{env.get('PATH', '')}"
    _run([str(go_bin), "install", jumlize_ref], env=env)
    
    go_bin_dir = Path.home() / "go" / "bin"
    installed_binary = go_bin_dir / "jumlize"
    if installed_binary.exists():
        symlink_path.parent.mkdir(parents=True, exist_ok=True)
        if not symlink_path.exists():
            symlink_path.symlink_to(installed_binary)
        print(f"{LOG_PREFIX} jumlize available at {symlink_path}")
        return symlink_path
    
    raise QuranSegmenterError("jumlize binary not found after installation")


def _persist_env(env_vars: Dict[str, str], env_file: Path):
    """Persist environment variables to a file and source it from bashrc."""
    lines = [f'export {k}="{v}"' for k, v in env_vars.items()]
    env_file.write_text("\n".join(lines) + "\n")
    
    bashrc = Path.home() / ".bashrc"
    marker = f"source {env_file}"
    if not bashrc.exists() or marker not in bashrc.read_text():
        with open(bashrc, "a", encoding="utf-8") as f:
            f.write(f"\n# Quran Segmenter env\n{marker}\n")
    
    try:
        profile_d = Path("/etc/profile.d/quran_segmenter.sh")
        profile_d.write_text(env_file.read_text())
    except PermissionError:
        # Not fatal; bashrc sourcing still works.
        pass


def setup_colab(
    words_path: str,
    metadata_path: str,
    config_path: str,
    base_dir: str = ".",
    rabtize_repo: str = "https://git.sr.ht/~rehandaphedar/rabtize",
    lafzize_repo: str = "https://git.sr.ht/~rehandaphedar/lafzize",
    go_url: str = "https://go.dev/dl/go1.25.5.linux-amd64.tar.gz",
    jumlize_ref: str = "git.sr.ht/~rehandaphedar/jumlize/v3@latest"
):
    """
    One-shot setup for Colab: installs rabtize, lafzize, jumlize, and wires env vars.
    """
    try:
        base_dir = Path(base_dir).expanduser().resolve()
        words = Path(words_path).expanduser().resolve()
        metadata = Path(metadata_path).expanduser().resolve()
        config_file = Path(config_path).expanduser().resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        
        if not words.exists():
            raise QuranSegmenterError(f"Words file not found at {words}")
        if not metadata.exists():
            raise QuranSegmenterError(f"Metadata file not found at {metadata}")
        
        rabtize_dir = base_dir / "rabtize"
        lafzize_dir = base_dir / "lafzize"
        
        # Clone + install rabtize
        _clone_repo(rabtize_repo, rabtize_dir)
        _patch_rabtize_pyproject(rabtize_dir / "pyproject.toml")
        _pip_install(["install", "-q", "-e", f"{rabtize_dir}/.[embed]"])
        
        # Clone + install lafzize
        _clone_repo(lafzize_repo, lafzize_dir)
        requirements = lafzize_dir / "requirements.txt"
        if requirements.exists():
            _pip_install(["install", "-q", "-r", str(requirements)])
        else:
            raise QuranSegmenterError(f"lafzize requirements not found at {requirements}")
        
        # Install Go + jumlize
        go_bin = _ensure_go(go_url)
        jumlize_bin = _install_jumlize(go_bin, jumlize_ref, Path("/usr/local/bin/jumlize"))
        
        # Copy resource files into expected locations
        shutil.copy2(words, lafzize_dir / words.name)
        shutil.copy2(words, rabtize_dir / words.name)
        shutil.copy2(metadata, lafzize_dir / metadata.name)
        
        # Persist environment variables
        env_vars = {
            "LAFZIZE_WORDS": str(words),
            "LAFZIZE_METADATA": str(metadata),
            "QURAN_SEGMENTER_CONFIG": str(config_file),
        }
        env_file = base_dir / "quran_segmenter_env.sh"
        _persist_env(env_vars, env_file)
        os.environ.update(env_vars)
        
        # Ensure config exists and points to the right paths
        cfg = Config.load_or_create(config_file)
        cfg.base_dir = base_dir
        cfg.lafzize_dir = lafzize_dir
        cfg.rabtize_dir = rabtize_dir
        cfg.jumlize_binary = jumlize_bin
        cfg.qpc_words_file = words
        cfg.quran_metadata_file = metadata
        cfg.save()
        
        print(f"{LOG_PREFIX} Setup complete.")
        print(f"{LOG_PREFIX} Config: {cfg.config_path}")
        print(f"{LOG_PREFIX} jumlize: {jumlize_bin}")
        print(f"{LOG_PREFIX} lafzize: {lafzize_dir}")
        print(f"{LOG_PREFIX} rabtize: {rabtize_dir}")
    
    except subprocess.CalledProcessError as e:
        raise QuranSegmenterError(f"Command failed ({' '.join(e.cmd)}): {e}") from e
    except Exception as e:
        if isinstance(e, QuranSegmenterError):
            raise
        raise QuranSegmenterError(str(e)) from e
