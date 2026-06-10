from typing import Dict
from settings.config import settings

_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "es": {
        "app_title": "DataPreview",
        "drop_files_here": "Arrastra archivos aquí",
        "tab_preview": "Preview",
        "tab_advanced": "Análisis avanzado",
        "tab_cleaning": "Limpieza",
        "tab_context": "Contexto",
        "theme_light": "Claro",
        "theme_dark": "Oscuro",
        "lang_es": "Español",
        "lang_en": "Inglés",
        "loading": "Cargando...",
        "estimated_time": "Tiempo est.",
        "error": "Error"
    },
    "en": {
        "app_title": "DataPreview",
        "drop_files_here": "Drop files here",
        "tab_preview": "Preview",
        "tab_advanced": "Advanced Analysis",
        "tab_cleaning": "Cleaning",
        "tab_context": "Context",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "lang_es": "Spanish",
        "lang_en": "English",
        "loading": "Loading...",
        "estimated_time": "Est. time",
        "error": "Error"
    }
}

def tr(key: str) -> str:
    """Devuelve la traducción de la clave según el idioma activo."""
    lang = settings.get("language")
    if lang not in _TRANSLATIONS:
        lang = "es" # por defecto
    
    return _TRANSLATIONS[lang].get(key, key)
