"""Lightweight .env loader and runtime configuration."""

import os
from pathlib import Path


def load_dotenv(env_path: Path | str = Path(".env")) -> None:
    """Load key=value pairs from .env into os.environ if not already set."""
    path = Path(env_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
