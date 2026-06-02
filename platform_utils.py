"""
platform_utils.py — V-Agent cross-platform helpers
All file I/O goes through here. Never use raw paths elsewhere.
"""

import os
import sys
import stat
import logging
import platform
import shutil
from pathlib import Path

logger = logging.getLogger("vagent.platform")

# ── App directories ────────────────────────────────────────────────────────────

def get_app_data_dir() -> Path:
    """Return the per-user config/data directory for V-Agent."""
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", Path.home())
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    path = Path(base) / "VAgent"
    ensure_dir(path)
    return path

def get_log_dir() -> Path:
    d = get_app_data_dir() / "logs"
    ensure_dir(d)
    return d

def get_config_path() -> Path:
    return get_app_data_dir() / "config.json"

def get_base_dir() -> Path:
    """Return the directory where vagent.py / the .exe lives."""
    if getattr(sys, "frozen", False):
        # PyInstaller / Nuitka compiled
        return Path(sys.executable).parent
    return Path(__file__).parent.resolve()

def get_resource_path(relative: str) -> Path:
    """Resolve a bundled asset path (works frozen and unfrozen)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).parent.resolve()
    return base / relative

# ── Dir / file helpers ─────────────────────────────────────────────────────────

def ensure_dir(path) -> Path:
    """Create directory (and parents) if it doesn't exist."""
    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        logger.error("Cannot create directory %s: %s", p, e)
    return p

def safe_open(path, mode="r", encoding="utf-8"):
    """Open a file with explicit UTF-8 encoding and safe newline handling."""
    p = Path(path)
    if "w" in mode or "a" in mode:
        ensure_dir(p.parent)
    nl = "" if "b" not in mode else None
    return open(p, mode, encoding=None if "b" in mode else encoding, newline=nl)

def atomic_write(path, content: str, encoding="utf-8"):
    """Write to a temp file then rename — prevents partial writes."""
    p    = Path(path)
    tmp  = p.with_suffix(p.suffix + ".tmp")
    ensure_dir(p.parent)
    try:
        tmp.write_text(content, encoding=encoding)
        tmp.replace(p)   # atomic on POSIX; near-atomic on Windows
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

def check_writable(path) -> bool:
    """Return True if the path (or its parent) is writable."""
    p = Path(path)
    target = p if p.exists() else p.parent
    return os.access(target, os.W_OK)

def check_disk_space(path, required_bytes: int = 10 * 1024 * 1024) -> bool:
    """Return True if there's at least required_bytes free at path."""
    try:
        free = shutil.disk_usage(Path(path).parent).free
        return free >= required_bytes
    except Exception:
        return True  # assume OK if we can't check

# ── .env helpers ───────────────────────────────────────────────────────────────

def load_env_file(path=None):
    """Load a .env file into os.environ (skips already-set keys)."""
    env_path = Path(path) if path else get_base_dir() / ".env"
    if not env_path.exists():
        return
    try:
        # Check for UTF-8 BOM (common Windows issue)
        raw = env_path.read_bytes()
        text = raw.decode("utf-8-sig")  # strips BOM if present
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, val)
    except Exception as e:
        logger.warning("Could not load .env: %s", e)

def write_env_key(key: str, value: str, path=None):
    """Safely update a single key in the .env file."""
    env_path = Path(path) if path else get_base_dir() / ".env"
    ensure_dir(env_path.parent)

    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8-sig").splitlines()

    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")

    atomic_write(env_path, "\n".join(lines) + "\n")

    # Restrict permissions on Linux/Mac
    if platform.system() != "Windows":
        try:
            env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
        except Exception:
            pass

# ── Logging setup ──────────────────────────────────────────────────────────────

def setup_logging(level=logging.INFO):
    """Configure rotating file + console logging."""
    import logging.handlers
    log_path = get_log_dir() / "vagent.log"
    handlers = [
        logging.handlers.TimedRotatingFileHandler(
            log_path, when="W0", backupCount=4, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )

# ── OS info ────────────────────────────────────────────────────────────────────

def is_windows() -> bool:
    return platform.system() == "Windows"

def is_linux() -> bool:
    return platform.system() == "Linux"

def is_mac() -> bool:
    return platform.system() == "Darwin"

def os_label() -> str:
    return f"{platform.system()} {platform.machine()} {platform.release()}"
