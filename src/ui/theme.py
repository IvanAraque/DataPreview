from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

# Global Fonts and Metrics
FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

COMMON_STYLE = """
* {
    font-family: %s;
    font-size: 14px;
}
/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background-color: #C1C1C1;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:horizontal {
    background-color: #C1C1C1;
    min-width: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
""" % FONT_FAMILY

LIGHT_THEME = COMMON_STYLE + """
QWidget {
    background-color: #FFFFFF;
    color: #111827;
}

/* Sidebar Area */
QWidget#sidebar {
    background-color: #F9FAFB;
    border-right: 1px solid #E5E7EB;
}
QListWidget#sidebarList {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget#sidebarList::item {
    color: #4B5563;
    padding: 12px 16px;
    border-radius: 6px;
    margin: 4px 8px;
}
QListWidget#sidebarList::item:hover {
    background-color: #F3F4F6;
    color: #111827;
}
QListWidget#sidebarList::item:selected {
    background-color: #EEF2FF;
    color: #4F46E5;
    font-weight: 600;
}

/* Top Bar */
QWidget#topbar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E5E7EB;
}

/* Drop Zone */
QLabel#dropLabel {
    color: #6B7280;
    font-size: 16px;
    border: 2px dashed #D1D5DB;
    border-radius: 12px;
    padding: 40px;
    background-color: #F9FAFB;
}

/* Progress Bar */
QProgressBar {
    background-color: #F3F4F6;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent; /* hide text */
    border: none;
}
QProgressBar::chunk {
    background-color: #4F46E5;
    border-radius: 4px;
}

/* Buttons */
QPushButton {
    background-color: #FFFFFF;
    color: #374151;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #F9FAFB;
    border-color: #9CA3AF;
}
QPushButton#primaryBtn {
    background-color: #4F46E5;
    color: #FFFFFF;
    border: none;
}
QPushButton#primaryBtn:hover {
    background-color: #4338CA;
}
QPushButton#iconBtn {
    border: none;
    background: transparent;
    padding: 4px;
}
QPushButton#iconBtn:hover {
    background-color: #F3F4F6;
    border-radius: 4px;
}

/* Tables and Trees */
QTableWidget, QTreeView {
    background-color: #FFFFFF;
    alternate-background-color: #F9FAFB;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    gridline-color: #F3F4F6;
    outline: none;
}
QTableWidget::item, QTreeView::item {
    padding: 8px;
    border-bottom: 1px solid #F3F4F6;
}
QTableWidget::item:selected, QTreeView::item:selected {
    background-color: #EEF2FF;
    color: #111827;
}
QHeaderView::section {
    background-color: #F9FAFB;
    color: #6B7280;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #E5E7EB;
    border-right: 1px solid #F3F4F6;
    font-weight: 600;
}
QTableCornerButton::section {
    background-color: #F9FAFB;
    border: none;
    border-bottom: 1px solid #E5E7EB;
    border-right: 1px solid #F3F4F6;
}

/* Combobox */
QComboBox {
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 6px 10px;
    background: white;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
}
QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #6B7280;
    margin-right: 5px;
}
"""

DARK_THEME = COMMON_STYLE + """
QWidget {
    background-color: #1E1E1E;
    color: #E5E7EB;
}

/* Sidebar Area */
QWidget#sidebar {
    background-color: #252526;
    border-right: 1px solid #333333;
}
QListWidget#sidebarList {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget#sidebarList::item {
    color: #9CA3AF;
    padding: 12px 16px;
    border-radius: 6px;
    margin: 4px 8px;
}
QListWidget#sidebarList::item:hover {
    background-color: #2A2D2E;
    color: #E5E7EB;
}
QListWidget#sidebarList::item:selected {
    background-color: #37373D;
    color: #818CF8;
    font-weight: 600;
}

/* Top Bar */
QWidget#topbar {
    background-color: #1E1E1E;
    border-bottom: 1px solid #333333;
}

/* Drop Zone */
QLabel#dropLabel {
    color: #9CA3AF;
    font-size: 16px;
    border: 2px dashed #4B5563;
    border-radius: 12px;
    padding: 40px;
    background-color: #252526;
}

/* Progress Bar */
QProgressBar {
    background-color: #374151;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
    border: none;
}
QProgressBar::chunk {
    background-color: #818CF8;
    border-radius: 4px;
}

/* Buttons */
QPushButton {
    background-color: #2D2D30;
    color: #E5E7EB;
    border: 1px solid #3E3E42;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #3E3E42;
    border-color: #555555;
}
QPushButton#primaryBtn {
    background-color: #4F46E5;
    color: #FFFFFF;
    border: none;
}
QPushButton#primaryBtn:hover {
    background-color: #4338CA;
}
QPushButton#iconBtn {
    border: none;
    background: transparent;
    padding: 4px;
}
QPushButton#iconBtn:hover {
    background-color: #333333;
    border-radius: 4px;
}

/* Tables and Trees */
QTableWidget, QTreeView {
    background-color: #1E1E1E;
    alternate-background-color: #252526;
    border: 1px solid #333333;
    border-radius: 6px;
    gridline-color: #333333;
    outline: none;
}
QTableWidget::item, QTreeView::item {
    padding: 8px;
    border-bottom: 1px solid #2D2D30;
}
QTableWidget::item:selected, QTreeView::item:selected {
    background-color: #37373D;
    color: #FFFFFF;
}
QHeaderView::section {
    background-color: #252526;
    color: #D1D5DB;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #333333;
    border-right: 1px solid #333333;
    font-weight: 600;
}
QTableCornerButton::section {
    background-color: #252526;
    border: none;
    border-bottom: 1px solid #333333;
    border-right: 1px solid #333333;
}

/* Combobox */
QComboBox {
    border: 1px solid #4B5563;
    border-radius: 6px;
    padding: 6px 10px;
    background: #252526;
    color: #E5E7EB;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
}
QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #9CA3AF;
    margin-right: 5px;
}
"""

def apply_theme(app: QApplication, theme_name: str) -> None:
    # Attempt to set default font
    font = QFont("Inter")
    if not font.exactMatch():
        font = QFont("Segoe UI")
    app.setFont(font)
    
    if theme_name == "dark":
        app.setStyleSheet(DARK_THEME)
    else:
        app.setStyleSheet(LIGHT_THEME)
