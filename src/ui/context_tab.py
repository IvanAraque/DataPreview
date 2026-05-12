from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QScrollArea, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt
import qtawesome as qta


def _type_meta(dtype_str: str):
    """Devuelve (icono qtawesome, color) según el tipo polars como string."""
    d = (dtype_str or "").lower()
    if any(t in d for t in ("int", "float", "decimal")):
        return ("fa5s.hashtag", "#4F46E5")
    if any(t in d for t in ("date", "time")):
        return ("fa5s.calendar-alt", "#10B981")
    if any(t in d for t in ("bool",)):
        return ("fa5s.toggle-on", "#F59E0B")
    if any(t in d for t in ("utf8", "string", "categorical", "cat")):
        return ("fa5s.font", "#EC4899")
    return ("fa5s.question-circle", "#6B7280")


class StatCard(QFrame):
    """Tarjeta de métrica clave (filas/columnas/memoria/tipos)."""

    def __init__(self, icon: str, label: str, value: str = "—", color: str = "#4F46E5"):
        super().__init__()
        self.setObjectName("statCard")
        self.setStyleSheet(
            "QFrame#statCard {"
            "  border: 1px solid rgba(127,127,127,0.15);"
            "  border-radius: 10px;"
            "  background: rgba(127,127,127,0.04);"
            "}"
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(140)

        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(2)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon, color=color).pixmap(14, 14))
        head.addWidget(icon_lbl)
        head_lbl = QLabel(label)
        head_lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
        head.addWidget(head_lbl)
        head.addStretch(1)
        v.addLayout(head)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        v.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)


class ContextTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._description_full = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        # Título
        self.title = QLabel("<b>Contexto del dataset</b>")
        self.title.setStyleSheet("font-size: 20px;")
        outer.addWidget(self.title)

        # Cards de resumen
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self.card_rows = StatCard("fa5s.list-ol", "Filas", "—", "#4F46E5")
        self.card_cols = StatCard("fa5s.columns", "Columnas", "—", "#10B981")
        self.card_mem = StatCard("fa5s.microchip", "Memoria", "—", "#F59E0B")
        self.card_types = StatCard("fa5s.layer-group", "Tipos", "—", "#EC4899")
        cards_row.addWidget(self.card_rows)
        cards_row.addWidget(self.card_cols)
        cards_row.addWidget(self.card_mem)
        cards_row.addWidget(self.card_types)
        outer.addLayout(cards_row)

        # Sección de diccionario / descripción (oculta si no se proporciona)
        self.desc_section = QFrame()
        self.desc_section.setObjectName("descSection")
        self.desc_section.setStyleSheet(
            "QFrame#descSection {"
            "  border: 1px solid rgba(79,70,229,0.18);"
            "  border-left: 3px solid #4F46E5;"
            "  border-radius: 8px;"
            "  background: rgba(79,70,229,0.04);"
            "}"
        )
        desc_v = QVBoxLayout(self.desc_section)
        desc_v.setContentsMargins(12, 8, 12, 10)
        desc_v.setSpacing(4)

        desc_head = QHBoxLayout()
        desc_head.setContentsMargins(0, 0, 0, 0)
        head_icon = QLabel()
        head_icon.setPixmap(qta.icon("fa5s.book", color="#4F46E5").pixmap(13, 13))
        desc_head.addWidget(head_icon)
        title_lbl = QLabel("<b>Descripción de los datos</b>")
        title_lbl.setStyleSheet("font-size: 12px; color: #4F46E5;")
        desc_head.addWidget(title_lbl)
        desc_head.addStretch(1)
        self.desc_toggle_btn = QPushButton("Ver más")
        self.desc_toggle_btn.setObjectName("iconBtn")
        self.desc_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.desc_toggle_btn.setStyleSheet("font-size: 11px; color: #4F46E5;")
        self.desc_toggle_btn.setVisible(False)
        self.desc_toggle_btn.clicked.connect(self._toggle_description)
        desc_head.addWidget(self.desc_toggle_btn)
        desc_v.addLayout(desc_head)

        self.desc_label = QLabel("")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("font-size: 12px; color: #374151;")
        desc_v.addWidget(self.desc_label)

        self._desc_expanded = False
        self._desc_short_limit = 280
        outer.addWidget(self.desc_section)
        self.desc_section.setVisible(False)

        # Cabecera de tabla
        cols_head = QHBoxLayout()
        cols_head.setContentsMargins(0, 0, 0, 0)
        cols_title = QLabel("<b>Columnas</b>")
        cols_title.setStyleSheet("font-size: 13px;")
        cols_head.addWidget(cols_title)
        cols_head.addStretch(1)
        self.cols_count_lbl = QLabel("")
        self.cols_count_lbl.setStyleSheet("color: #6B7280; font-size: 12px;")
        cols_head.addWidget(self.cols_count_lbl)
        outer.addLayout(cols_head)

        # Tabla de columnas (más limpia, redimensionable)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Columna", "Tipo", "Nulos", "Únicos", "Mínimo", "Máximo"])
        # Todas las columnas Interactive (arrastrables) con anchos por defecto razonables
        header = self.table.horizontalHeader()
        for i in range(6):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 200)  # Nombre de columna
        self.table.setColumnWidth(1, 110)  # Tipo
        self.table.setColumnWidth(2, 110)  # Nulos
        self.table.setColumnWidth(3, 90)   # Únicos
        self.table.setColumnWidth(4, 110)  # Mínimo
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        outer.addWidget(self.table, 1)

    # --- API --------------------------------------------------------------

    def update_profile(self, profile: dict, context_text: str = ""):
        if not profile:
            self.card_rows.set_value("—")
            self.card_cols.set_value("—")
            self.card_mem.set_value("—")
            self.card_types.set_value("—")
            self.cols_count_lbl.setText("")
            self.table.setRowCount(0)
            self._set_description("")
            return

        rows = profile.get("rows", 0)
        cols = profile.get("cols", 0)
        mem = profile.get("memory_mb", 0)
        columns = profile.get("columns", [])

        self.card_rows.set_value(f"{rows:,}".replace(",", "."))
        self.card_cols.set_value(str(cols))
        self.card_mem.set_value(f"{mem} MB")
        # Conteo de tipos únicos (basado en el string del dtype)
        type_set = set()
        for c in columns:
            type_set.add(str(c.get("type", "")).split("(")[0].strip())
        self.card_types.set_value(str(len(type_set)))
        self.cols_count_lbl.setText(f"{len(columns)} columnas")

        # Descripción (diccionario) si la hay
        self._set_description(context_text or "")

        # Tabla
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(columns))
        for i, col in enumerate(columns):
            name = str(col.get("name", ""))
            dtype = str(col.get("type", ""))

            # Columna 0: nombre + icono de tipo
            name_item = QTableWidgetItem(name)
            icon_name, color = _type_meta(dtype)
            name_item.setIcon(qta.icon(icon_name, color=color))
            self.table.setItem(i, 0, name_item)

            self.table.setItem(i, 1, QTableWidgetItem(dtype))
            self.table.setItem(i, 2, QTableWidgetItem(str(col.get("nulls", ""))))

            unique_item = QTableWidgetItem()
            unique_item.setData(Qt.DisplayRole, col.get("unique", ""))
            self.table.setItem(i, 3, unique_item)

            self.table.setItem(i, 4, QTableWidgetItem(str(col.get("min", ""))))
            self.table.setItem(i, 5, QTableWidgetItem(str(col.get("max", ""))))
        self.table.setSortingEnabled(True)

    # --- Diccionario ------------------------------------------------------

    def _set_description(self, text: str):
        text = (text or "").strip()
        self._description_full = text
        if not text:
            self.desc_section.setVisible(False)
            return
        self.desc_section.setVisible(True)
        self._desc_expanded = False
        if len(text) > self._desc_short_limit:
            short = text[: self._desc_short_limit].rstrip() + "…"
            self.desc_label.setText(short)
            self.desc_toggle_btn.setText("Ver más")
            self.desc_toggle_btn.setVisible(True)
        else:
            self.desc_label.setText(text)
            self.desc_toggle_btn.setVisible(False)

    def _toggle_description(self):
        if not self._description_full:
            return
        if self._desc_expanded:
            short = self._description_full[: self._desc_short_limit].rstrip() + "…"
            self.desc_label.setText(short)
            self.desc_toggle_btn.setText("Ver más")
        else:
            self.desc_label.setText(self._description_full)
            self.desc_toggle_btn.setText("Ver menos")
        self._desc_expanded = not self._desc_expanded
