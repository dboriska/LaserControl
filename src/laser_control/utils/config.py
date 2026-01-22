import toml
import os
from typing import Dict, Any

SETTINGS_PATH = os.path.join(os.getcwd(), "config", "settings.toml")


def load_settings() -> Dict[str, Any]:
    """Load settings from TOML file, returning defaults on failure."""
    try:
        if os.path.exists(SETTINGS_PATH):
            return toml.load(SETTINGS_PATH)
    except Exception as e:
        print(f"Error loading settings: {e}")
    return {}  # Return empty dict fallback


def save_settings(settings: Dict[str, Any]):
    """Save settings dictionary to TOML file."""
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            toml.dump(settings, f)
    except Exception as e:
        print(f"Error saving settings: {e}")


def get_last_working_dir() -> str:
    """Convenience getter for working directory."""
    s = load_settings()
    return s.get("general", {}).get("last_working_directory", os.getcwd())


def set_last_working_dir(path: str):
    """Convenience setter for working directory."""
    s = load_settings()
    if "general" not in s:
        s["general"] = {}
    s["general"]["last_working_directory"] = path
    save_settings(s)
