"""Local-only credentials and explicit radio/lab configuration."""

import json
import os
from pathlib import Path


def load_config(data_dir):
    path = Path(data_dir) / "config.json"
    config = {}
    if path.is_file():
        if path.stat().st_size > 16384:
            raise RuntimeError("config.json excede 16 KB")
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raise RuntimeError("config.json invalido") from None
        if not isinstance(config, dict):
            raise RuntimeError("config.json invalido")
    config["wdgwars_api_key"] = os.environ.get(
        "HACKOMON_WDGWARS_API_KEY", config.get("wdgwars_api_key", ""))
    return config
