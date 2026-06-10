import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.theme import apply_theme
from settings.config import settings

def main():
    # Desactiva GPU y sandbox de WebEngine para máxima estabilidad en Windows
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --no-sandbox"
    
    app = QApplication(sys.argv)
    
    current_theme = settings.get("theme")
    apply_theme(app, current_theme)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
