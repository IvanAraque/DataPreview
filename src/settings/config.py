import json
import os
from pathlib import Path
from typing import Any, Dict

class SettingsManager:
    """Gestiona la configuración de la app guardada en un archivo JSON."""
    
    def __init__(self):
        # Directorio AppData según el SO
        appdata_dir = os.environ.get("APPDATA")
        if not appdata_dir:
            # Fallback al home local si APPDATA no está disponible
            appdata_dir = str(Path.home() / ".config")
            
        self.config_dir = Path(appdata_dir) / "DataPreview"
        self.config_file = self.config_dir / "settings.json"
        
        self._default_settings = {
            "theme": "light",
            "language": "es"
        }
        
        self._settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Carga la configuración del JSON o devuelve los valores por defecto si no existe."""
        if not self.config_file.exists():
            return self._default_settings.copy()
            
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Combinar con los valores por defecto por si faltan claves
                settings = self._default_settings.copy()
                settings.update(data)
                return settings
        except Exception:
            return self._default_settings.copy()

    def _save_settings(self) -> None:
        """Guarda la configuración actual en el archivo JSON."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4)
        except Exception as e:
            # los logs se gestionan en otro sitio; guardar settings no debe tirar la app
            pass

    def get(self, key: str) -> Any:
        return self._settings.get(key, self._default_settings.get(key))

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self._save_settings()

# Instancia global
settings = SettingsManager()
