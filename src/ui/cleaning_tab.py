from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QHBoxLayout, QPushButton
)
from PySide6.QtCore import Qt
import qtawesome as qta


class SortableTreeItem(QTreeWidgetItem):
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column == 1:
            sev_map = {"Alta": 3, "Media": 2, "Baja": 1, "": 0}
            return sev_map.get(self.text(1), 0) < sev_map.get(other.text(1), 0)
        # Compare text directly to avoid PySide6 infinite recursion bug with super().__lt__
        return self.text(column) < other.text(column)


class CleaningTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)

        self.top_layout = QHBoxLayout()
        self.title = QLabel("Recomendaciones de Limpieza")
        self.title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        self.top_layout.addWidget(self.title)

        # Estado de la IA (loading / OK / error)
        self.ai_status_lbl = QLabel("")
        self.ai_status_lbl.setStyleSheet("color: #6B7280; font-size: 12px; margin-left: 10px;")
        self.top_layout.addWidget(self.ai_status_lbl)

        self.top_layout.addStretch()

        self.collapse_btn = QPushButton("Minimizar Todo")
        self.collapse_btn.setObjectName("iconBtn")
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        self.top_layout.addWidget(self.collapse_btn)

        self.layout.addLayout(self.top_layout)
        self.is_collapsed = False

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Columna / Problema", "Severidad", "Sugerencia"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tree.setColumnWidth(0, 280)
        self.tree.setColumnWidth(1, 90)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QTreeWidget.NoSelection)
        self.tree.setSortingEnabled(True)
        self.layout.addWidget(self.tree)

        # Cache de las recomendaciones heurísticas mostradas, para no perderlas al añadir las IA
        self._heuristic_recs = []
        self._ai_recs = []

    # --- API pública -----------------------------------------------------

    def update_recommendations(self, recs: list):
        """Carga las recomendaciones heurísticas (las de cleaner.py)."""
        self._heuristic_recs = list(recs or [])
        self._rebuild_tree()

    def set_ai_loading(self, loading: bool):
        if loading:
            self.ai_status_lbl.setText("⏳ La IA está revisando los datos...")
            self.ai_status_lbl.setStyleSheet("color: #4F46E5; font-size: 12px; margin-left: 10px;")
        else:
            if self._ai_recs:
                self.ai_status_lbl.setText("✓ Análisis IA incluido")
                self.ai_status_lbl.setStyleSheet("color: #10B981; font-size: 12px; margin-left: 10px;")
            else:
                self.ai_status_lbl.setText("")

    def set_ai_recommendations(self, recs: list):
        """Añade las recomendaciones IA al tree (con badge)."""
        self._ai_recs = list(recs or [])
        for r in self._ai_recs:
            r.setdefault("origen", "ia")
        self._rebuild_tree()
        self.set_ai_loading(False)

    def set_ai_error(self, msg: str):
        self._ai_recs = []
        self.ai_status_lbl.setText("⚠ IA: " + (msg or "error"))
        self.ai_status_lbl.setStyleSheet("color: #EF4444; font-size: 12px; margin-left: 10px;")

    # --- Internos --------------------------------------------------------

    def _toggle_collapse(self):
        if self.is_collapsed:
            self.tree.expandAll()
            self.collapse_btn.setText("Minimizar Todo")
        else:
            self.tree.collapseAll()
            self.collapse_btn.setText("Expandir Todo")
        self.is_collapsed = not self.is_collapsed

    def _rebuild_tree(self):
        self.tree.setSortingEnabled(False)
        self.tree.clear()

        all_recs = list(self._heuristic_recs) + list(self._ai_recs)
        if not all_recs:
            item = SortableTreeItem(["No se encontraron problemas evidentes.", "", ""])
            self.tree.addTopLevelItem(item)
            self.tree.setSortingEnabled(True)
            return

        # Agrupar por columna
        grouped = {}
        for rec in all_recs:
            col = rec.get("columna", "?")
            grouped.setdefault(col, []).append(rec)

        for col, problems in grouped.items():
            sev_levels = [p.get("severidad", "Baja") for p in problems]
            if "Alta" in sev_levels:
                max_sev = "Alta"
            elif "Media" in sev_levels:
                max_sev = "Media"
            else:
                max_sev = "Baja"

            col_item = SortableTreeItem([col, max_sev, ""])
            col_item.setIcon(0, qta.icon("fa5s.columns", color="#6B7280"))
            font = col_item.font(0)
            font.setBold(True)
            col_item.setFont(0, font)

            for prob in problems:
                sev = prob.get("severidad", "Baja")
                origen = prob.get("origen", "auto")
                badge = "  [IA]" if origen == "ia" else ""
                child = SortableTreeItem([
                    prob.get("problema", "") + badge,
                    sev,
                    prob.get("sugerencia", ""),
                ])
                if sev == "Alta":
                    child.setIcon(1, qta.icon("fa5s.exclamation-circle", color="#EF4444"))
                elif sev == "Media":
                    child.setIcon(1, qta.icon("fa5s.exclamation-triangle", color="#F59E0B"))
                else:
                    child.setIcon(1, qta.icon("fa5s.info-circle", color="#3B82F6"))

                # Marcar visualmente las de IA
                if origen == "ia":
                    f = child.font(0)
                    f.setItalic(True)
                    child.setFont(0, f)
                    child.setForeground(0, child.foreground(0))  # palette default

                col_item.addChild(child)

            self.tree.addTopLevelItem(col_item)
            col_item.setExpanded(True)

        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(1, Qt.DescendingOrder)
