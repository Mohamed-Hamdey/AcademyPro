"""
Config loader.
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from paths import AppPaths, bundled_path
CONFIG_PATH = AppPaths.config_file()
_config_cache = None


def load_config() -> dict:
    """Load academy_config.json, caching it after the first read."""
    global _config_cache
    if _config_cache is None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
    return _config_cache


def get_plan(plan_type: str) -> dict:
    config = load_config()
    plan = config["plans"].get(plan_type)
    if plan is None:
        raise ValueError(f"Unknown plan type: {plan_type!r}")
    return plan





def get_academy_name() -> str:
    return load_config()["academy_name"]


def get_academy_logo() -> str | None:
    """
    Absolute path to the academy logo, or None if not configured / missing.
    Relative paths in the config are resolved against the project root
    (which, when frozen, is the bundle's temp extraction folder).
    """
    raw = load_config().get("logo_path")
    if not raw:
        return None
    if os.path.isabs(raw):
        path = raw
    else:
        path = bundled_path(raw)
    return path if os.path.exists(path) else None


def get_plan_label(plan_type: str) -> str:
    """Localized plan label. Arabic if active and available, else English."""
    from ui import i18n
    plan = get_plan(plan_type)
    if i18n.current_language() == "ar" and "label_ar" in plan:
        return plan["label_ar"]
    return plan["label"]


def get_group(group_key: str) -> dict:
    config = load_config()
    group = config.get("session_times", {}).get(group_key)
    if group is None:
        raise ValueError(f"Unknown session time: {group_key!r}")
    return group

def get_group_label(group_key: str) -> str:
    from ui import i18n
    group = get_group(group_key)
    if i18n.current_language() == "ar" and "label_ar" in group:
        return group["label_ar"]
    return group["label"]