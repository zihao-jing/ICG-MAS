"""Configuration loader for SILO-BENCH.

Reads API credentials and model settings from configs/config.yaml.
Falls back to environment variables and CLI arguments.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# PyYAML is used for config loading
import yaml

# Default config file path (relative to project root)
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "configs"
_CONFIG_FILE = _CONFIG_DIR / "config.yaml"


def _find_config_file() -> Path | None:
    """Locate the config file, checking several paths."""
    candidates = [
        _CONFIG_FILE,
        Path("configs/config.yaml"),
        Path.home() / ".silo-bench" / "config.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def load_config(profile: str = "default") -> dict[str, str]:
    """Load model configuration from config.yaml or environment variables.

    Resolution order (highest priority first):
        1. Environment variables: SILO_API_BASE, SILO_API_KEY, SILO_MODEL
        2. Profile section in config.yaml
        3. Default section in config.yaml

    Args:
        profile: Name of the profile to load. Use "default" for the
                 top-level default section.

    Returns:
        Dict with keys: api_base, api_key, model
    """
    config: dict[str, Any] = {}

    cfg_path = _find_config_file()
    if cfg_path is not None:
        with open(cfg_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # Start from the default section
    result = {
        "api_base": "",
        "api_key": "",
        "model": "",
    }

    if "default" in config:
        for key in result:
            if key in config["default"]:
                result[key] = str(config["default"][key])

    # Override with profile if specified and not "default"
    if profile != "default" and "profiles" in config:
        prof = config["profiles"].get(profile, {})
        for key in result:
            if key in prof:
                result[key] = str(prof[key])

    # Environment variables take highest priority
    env_map = {
        "api_base": "SILO_API_BASE",
        "api_key": "SILO_API_KEY",
        "model": "SILO_MODEL",
    }
    for key, env_var in env_map.items():
        val = os.environ.get(env_var)
        if val:
            result[key] = val

    return result
