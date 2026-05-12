import json
import os
from pathlib import Path
from typing import Any, Dict

class SettingsManager:
    """Manages application settings stored in a JSON file."""
    
    def __init__(self):
        # Determine the AppData directory based on OS
        appdata_dir = os.environ.get("APPDATA")
        if not appdata_dir:
            # Fallback to local home if APPDATA is not available
            appdata_dir = str(Path.home() / ".config")
            
        self.config_dir = Path(appdata_dir) / "DataPreview"
        self.config_file = self.config_dir / "settings.json"
        
        self._default_settings = {
            "theme": "light",
            "language": "es"
        }
        
        self._settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Loads settings from the JSON file or returns defaults if it doesn't exist."""
        if not self.config_file.exists():
            return self._default_settings.copy()
            
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge with defaults in case of missing keys
                settings = self._default_settings.copy()
                settings.update(data)
                return settings
        except Exception:
            return self._default_settings.copy()

    def _save_settings(self) -> None:
        """Saves current settings to the JSON file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4)
        except Exception as e:
            # logs will be handled elsewhere, but settings save shouldn't crash app
            pass

    def get(self, key: str) -> Any:
        return self._settings.get(key, self._default_settings.get(key))

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self._save_settings()

# Global instance for easy access
settings = SettingsManager()
