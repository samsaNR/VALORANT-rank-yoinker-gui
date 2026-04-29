"""Lightweight config helpers for the GUI.

These do not depend on the network or on any of the runtime classes from the
console app, so they are safe to import early and are easy to unit-test.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict

from src.constants import DEFAULT_CONFIG

CONFIG_FILE = "config.json"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base``.

    Nested dicts (e.g. ``table``, ``flags``) are merged key-by-key so the
    user's existing config is preserved when new defaults are added upstream.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: str = CONFIG_FILE) -> Dict[str, Any]:
    """Return the user config merged on top of ``DEFAULT_CONFIG``.

    Missing or malformed files fall back to the defaults so the GUI never
    crashes on first launch.
    """
    if not os.path.exists(path):
        return copy.deepcopy(DEFAULT_CONFIG)

    try:
        with open(path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(DEFAULT_CONFIG)

    if not isinstance(user_config, dict):
        return copy.deepcopy(DEFAULT_CONFIG)

    return _deep_merge(DEFAULT_CONFIG, user_config)


def save_config(config: Dict[str, Any], path: str = CONFIG_FILE) -> None:
    """Persist ``config`` to ``path`` using the same formatting as the CLI."""
    merged = _deep_merge(DEFAULT_CONFIG, config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=4)
