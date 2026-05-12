from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QVBoxLayout, QComboBox, QHBoxLayout, QPushButton,
    QFrame, QMenu, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal
import polars as pl
import qtawesome as qta
from charts.selector import select_charts
from charts.renderer import create_chart_widget
from settings.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TYPE_ICONS = {
    "hist": "fa5s.align-left",
    "bar": "fa5s.chart-bar",
    "scatter": "fa5s.braille",
    "line": "fa5s.chart-line",
}


def _explain_colors() -> dict:
    """Colores theme-aware para el bloque de análisis IA. Visibles en ambos."""
    if settings.get("theme") == "dark":
        return {
            "accent": "#A5B4FC",         # indigo-300 (cabecera)
            "description": "#C7D2FE",    # indigo-200 (italic)
            "observations": "#E5E7EB",   # gray-200
        }
    return {
        "accent": "#4F46E5",             # indigo-600
        "description": "#4338CA",        # indigo-700 (italic)
        "observations": "#1F2937",       # gray-800
    }


def _col_is_numeric(df: pl.DataFrame, col: str) -> bool:
    try:
        return col in df.columns and df[col].dtype in pl.NUMERIC_DTYPES
    except Exception:
        return False


def _col_is_temporal(df: pl.DataFrame, col: str) -> bool:
    try:
        return col in df.columns and df[col].dtype in (pl.Date, pl.Datetime)
    except Exception:
        return False


_TYPE_LABELS = [
    ("hist", "Histograma"),
    ("bar", "Barras"),
    ("scatter", "Dispersión"),
    ("line", "Línea"),
]


def _is_compatible(df: pl.DataFrame, ctype: str, x: str, y: str = None) -> bool:
    """¿La combinación tipo+x+y es renderizable?"""
    if x not in df.columns:
        return False
    x_num = _col_is_numeric(df, x)
    x_time = _col_is_temporal(df, x)
    if ctype == "hist":
        return x_num or x_time
    if ctype == "bar":
        return True  # bar admite cualquier x (frecuencia)
    if ctype == "scatter":
        if not y or y not in df.columns or y == x:
            return False
        return x_num and _col_is_numeric(df, y)
    if ctype == "line":
        if not y or y not in df.columns or y == x:
            return False
        return (x_num or x_time) and _col_is_numeric(df, y)
    return False


def _first_compatible_column(df: pl.DataFrame, role: str, exclude: list = None) -> str:
    """Devuelve la primera columna que encaja en `role`:
       'num' (numérica), 'time' (date/datetime), 'any' (cualquiera).
       `exclude` evita repetir columnas ya usadas.
    """
    exclude = set(exclude or [])
    for c in df.columns:
        if c in exclude:
            continue
        if role == "num" and _col_is_numeric(df, c):
            return c
        if role == "time" and _col_is_temporal(df, c):
            return c
        if role == "any":
            return c
    # Si no hay coincidencia exacta, devolver la primera disponible
    for c in df.columns:
        if c not in exclude:
            return c
    return df.columns[0] if df.columns else ""


def _autofix_for_type(df: pl.DataFrame, ctype: str, x: str, y: str = None) -> tuple:
    """
    Dado un tipo y X/Y deseados, devuelve (x', y') compatibles con el tipo.
    - Mantiene la elección del usuario si ya es válida.
    - Si no, busca la primera columna compatible.
    """
    if ctype == "hist":
        if not (_col_is_numeric(df, x) or _col_is_temporal(df, x)):
            x = _first_compatible_column(df, "num") or _first_compatible_column(df, "time") or x
        return x, None
    if ctype == "bar":
        # Cualquier X vale para bar; no necesita Y
        if x not in df.columns:
            x = _first_compatible_column(df, "any")
        return x, None
    if ctype == "scatter":
        if not _col_is_numeric(df, x):
            x = _first_compatible_column(df, "num", exclude=[y] if y else None) or x
        if not y or y == x or not _col_is_numeric(df, y):
            y = _first_compatible_column(df, "num", exclude=[x])
        return x, y
    if ctype == "line":
        # Preferimos x temporal; si no hay, num
        if not (_col_is_numeric(df, x) or _col_is_temporal(df, x)):
            x = (_first_compatible_column(df, "time", exclude=[y] if y else None)
                 or _first_compatible_column(df, "num", exclude=[y] if y else None) or x)
        if not y or y == x or not _col_is_numeric(df, y):
            y = _first_compatible_column(df, "num", exclude=[x])
        return x, y
    return x, y


def _normalize_chart_def(df: pl.DataFrame, x: str, y: str = None,
                        preferred_type: str = None) -> dict:
    """
    Devuelve un chart_def válido para las columnas dadas, intentando respetar
    el `preferred_type` si la combinación lo permite.
    """
    if x not in df.columns:
        return {"type": "hist", "x": x}

    # 1) Si el tipo preferido es compatible con las variables tal cual, lo usamos
    if preferred_type and _is_compatible(df, preferred_type, x, y):
        if preferred_type in ("scatter", "line"):
            return {"type": preferred_type, "x": x, "y": y}
        return {"type": preferred_type, "x": x,
                "y": "frequency" if preferred_type == "hist" else "count"}

    # 2) Auto-inferir según tipos
    x_num = _col_is_numeric(df, x)
    x_time = _col_is_temporal(df, x)
    x_cat = not (x_num or x_time)

    if y and y in df.columns and y != x:
        y_num = _col_is_numeric(df, y)
        if x_time and y_num:
            return {"type": "line", "x": x, "y": y}
        if x_num and y_num:
            return {"type": "scatter", "x": x, "y": y}
        if x_cat and y_num:
            return {"type": "bar", "x": x, "y": "count"}
        if x_num and not y_num:
            return {"type": "hist", "x": x, "y": "frequency"}
        return {"type": "bar", "x": x, "y": "count"}

    # Una sola columna
    if x_num or x_time:
        return {"type": "hist", "x": x, "y": "frequency"}
    return {"type": "bar", "x": x, "y": "count"}


def _spec_title(spec: dict) -> str:
    ctype = spec.get("type", "?")
    x = spec.get("x", "?")
    y = spec.get("y") if spec.get("y") not in (None, "count", "frequency") else None
    label_map = {"hist": "Distribución", "bar": "Frecuencia", "scatter": "Relación", "line": "Evolución"}
    base = label_map.get(ctype, ctype)
    if y:
        return f"{base}: {x} vs {y}"
    return f"{base}: {x}"


# ---------------------------------------------------------------------------
# Panel principal (gráfico + explicación + menu de reemplazo)
# ---------------------------------------------------------------------------

class ChartPanel(QWidget):
    """
    Un panel con un gráfico. Combo X siempre visible; combo Y solo cuando el
    gráfico es scatter/line. Al cambiar X o Y se normaliza al tipo de gráfico
    coherente con los tipos de las columnas elegidas.
    """

    # Emitido cuando el usuario elige reemplazar este panel por una alternativa
    replace_requested = Signal(int, int)  # (panel_index, alt_index)

    # Emitido cuando el usuario cambia las variables del panel
    spec_changed = Signal(object)  # self

    def __init__(self, df: pl.DataFrame, chart_def: dict, panel_index: int,
                 explanation: str = "", source: str = "auto"):
        super().__init__()
        self.df = df
        self._chart_def = dict(chart_def)
        self._explanation = explanation
        self._panel_index = panel_index
        self._source = source
        self._alternatives = []  # lista de specs alternativas (para el menú)
        self._ai_observations_cache = ""  # se preserva al cambiar variable

        self.setObjectName("chartPanel")
        self.setStyleSheet(
            "QWidget#chartPanel {"
            "  border: 1px solid rgba(127,127,127,0.18);"
            "  border-radius: 10px;"
            "  background: transparent;"
            "}"
        )
        # Ancho mínimo: que no se aplasten cuando la ventana es pequeña;
        # el alto se calcula a partir del chart_container y el bloque IA.
        self.setMinimumWidth(380)

        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(12, 10, 12, 12)
        self.v.setSpacing(6)

        # Cabecera: Tipo + X + Y + reemplazar.
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)

        # Combo de tipo (el usuario puede forzar el tipo manualmente)
        self.type_combo = QComboBox()
        for tcode, tlabel in _TYPE_LABELS:
            self.type_combo.addItem(tlabel, tcode)
        current_type = chart_def.get("type", "hist")
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == current_type:
                self.type_combo.setCurrentIndex(i)
                break
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        top.addWidget(self.type_combo)

        top.addWidget(QLabel("X:"))
        self.x_combo = QComboBox()
        self.x_combo.addItems(df.columns)
        if chart_def.get("x") in df.columns:
            self.x_combo.setCurrentText(chart_def["x"])
        self.x_combo.currentTextChanged.connect(self._on_x_changed)
        top.addWidget(self.x_combo, 1)

        self.y_label = QLabel("Y:")
        top.addWidget(self.y_label)
        self.y_combo = QComboBox()
        self.y_combo.addItems(df.columns)
        current_y = chart_def.get("y")
        if current_y and current_y in df.columns and current_y not in ("count", "frequency"):
            self.y_combo.setCurrentText(current_y)
        self.y_combo.currentTextChanged.connect(self._on_y_changed)
        top.addWidget(self.y_combo, 1)

        # Mostrar/ocultar el combo Y según el tipo actual
        self._update_y_visibility()

        self.replace_btn = QPushButton(qta.icon("fa5s.exchange-alt", color="#6B7280"), "")
        self.replace_btn.setToolTip("Reemplazar este gráfico por una alternativa de la IA")
        self.replace_btn.setFixedSize(28, 26)
        self.replace_btn.setCursor(Qt.PointingHandCursor)
        self.replace_btn.clicked.connect(self._on_replace_clicked)
        self.replace_btn.setVisible(False)
        top.addWidget(self.replace_btn)
        self.v.addLayout(top)

        # Gráfico
        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        # Alto FIJO del área del gráfico (setMinimumHeight no basta porque el
        # PlotWidget de pyqtgraph fuerza su sizeHint y ignora el floor).
        self.chart_container.setFixedHeight(300)
        self.v.addWidget(self.chart_container, 1)

        # Bloque IA: descripción + observaciones (theme-aware, visible en ambos temas).
        colors = _explain_colors()
        self.explanation_box = QFrame()
        self.explanation_box.setObjectName("explanationBox")
        self.explanation_box.setStyleSheet(
            "QFrame#explanationBox {"
            "  border: 1px solid rgba(79,70,229,0.22);"
            f"  border-left: 3px solid {colors['accent']};"
            "  border-radius: 6px;"
            "  background: rgba(79,70,229,0.06);"
            "}"
        )
        exp_layout = QVBoxLayout(self.explanation_box)
        exp_layout.setContentsMargins(10, 6, 10, 8)
        exp_layout.setSpacing(4)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.robot", color=colors["accent"]).pixmap(12, 12))
        head.addWidget(icon_lbl)
        self.exp_status_lbl = QLabel("Análisis de la IA")
        self.exp_status_lbl.setStyleSheet(
            f"font-size: 11px; color: {colors['accent']}; font-weight: 600; background: transparent;"
        )
        head.addWidget(self.exp_status_lbl)
        head.addStretch(1)
        exp_layout.addLayout(head)

        self.description_label = QLabel(explanation or "")
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet(
            f"font-size: 12px; font-style: italic; color: {colors['description']}; background: transparent;"
        )
        exp_layout.addWidget(self.description_label)

        self.observations_label = QLabel("")
        self.observations_label.setWordWrap(True)
        self.observations_label.setStyleSheet(
            f"font-size: 12px; padding-top: 2px; color: {colors['observations']}; background: transparent;"
        )
        exp_layout.addWidget(self.observations_label)

        self.explanation_box.setVisible(bool(explanation) and source == "ai")
        self.v.addWidget(self.explanation_box)

        self._render()

    # --- API ------------------------------------------------------------

    def set_alternatives(self, alts: list):
        """Lista de specs alternativas para mostrar en el menú de reemplazo."""
        self._alternatives = list(alts) if alts else []
        self.replace_btn.setVisible(bool(self._alternatives))

    def current_spec(self) -> dict:
        return dict(self._chart_def)

    def set_chart_min_height(self, h: int):
        """Permite al PreviewTab ajustar el alto del área del gráfico.
        Usa setFixedHeight para que el cambio sea visible: con setMinimumHeight
        el PlotWidget de pyqtgraph mantiene su sizeHint propio.
        """
        try:
            self.chart_container.setFixedHeight(int(h))
        except Exception:
            pass

    def show_observations_loading(self):
        """Muestra estado 'Cargando análisis...' en el bloque IA."""
        self.explanation_box.setVisible(True)
        self.exp_status_lbl.setText("Analizando con IA…")
        self.observations_label.setText("La IA está revisando el gráfico, un momento…")

    def set_ai_observations(self, observations: str, description: str = ""):
        """Inserta las observaciones (y opcionalmente actualiza la descripción)."""
        if description:
            self.description_label.setText(description)
        self.exp_status_lbl.setText("Análisis de la IA")
        self.observations_label.setText(observations or "")
        self.explanation_box.setVisible(True)

    def set_ai_error(self):
        """En caso de error, mantiene la descripción si la había y limpia observaciones."""
        self.exp_status_lbl.setText("Análisis de la IA")
        self.observations_label.setText("")
        # Si no hay nada que mostrar (ni descripción ni observaciones), ocultamos
        if not self.description_label.text() and not self.observations_label.text():
            self.explanation_box.setVisible(False)

    # --- Internos -------------------------------------------------------

    def _on_replace_clicked(self):
        if not self._alternatives:
            return
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { padding: 4px; } QMenu::item { padding: 6px 12px; }")
        for i, alt in enumerate(self._alternatives):
            title = _spec_title(alt)
            explanation = alt.get("explanation", "")
            icon = qta.icon(_TYPE_ICONS.get(alt.get("type", ""), "fa5s.chart-area"), color="#6B7280")
            label = title + ("  —  " + explanation[:60] + ("…" if len(explanation) > 60 else "")) if explanation else title
            act = menu.addAction(icon, label)
            act.setData(i)
        chosen = menu.exec(self.replace_btn.mapToGlobal(self.replace_btn.rect().bottomLeft()))
        if chosen:
            idx = chosen.data()
            if idx is not None:
                self.replace_requested.emit(self._panel_index, int(idx))

    def _current_x(self):
        return self.x_combo.currentText() if hasattr(self, "x_combo") else None

    def _current_y(self):
        return self.y_combo.currentText() if hasattr(self, "y_combo") else None

    def _current_type(self):
        if hasattr(self, "type_combo"):
            return self.type_combo.itemData(self.type_combo.currentIndex())
        return self._chart_def.get("type", "hist")

    def _update_y_visibility(self):
        """Mostrar Y solo cuando el tipo lo necesita (scatter/line)."""
        ctype = self._current_type() if hasattr(self, "type_combo") else self._chart_def.get("type")
        needs_y = ctype in ("scatter", "line")
        if hasattr(self, "y_combo"):
            self.y_combo.setVisible(needs_y)
        if hasattr(self, "y_label"):
            self.y_label.setVisible(needs_y)

    def _set_combos_silently(self, ctype: str, x: str, y: str = None):
        """Sincroniza los combos con el chart_def sin disparar señales."""
        if hasattr(self, "type_combo"):
            self.type_combo.blockSignals(True)
            for i in range(self.type_combo.count()):
                if self.type_combo.itemData(i) == ctype:
                    self.type_combo.setCurrentIndex(i)
                    break
            self.type_combo.blockSignals(False)
        if hasattr(self, "x_combo") and x and x in self.df.columns:
            self.x_combo.blockSignals(True)
            self.x_combo.setCurrentText(x)
            self.x_combo.blockSignals(False)
        if hasattr(self, "y_combo") and y and y in self.df.columns:
            self.y_combo.blockSignals(True)
            self.y_combo.setCurrentText(y)
            self.y_combo.blockSignals(False)
        self._update_y_visibility()

    def _apply_chart_def(self, new_def: dict, notify: bool = True):
        """Aplica un chart_def, sincroniza combos, repinta y notifica si toca."""
        self._chart_def = dict(new_def)
        ctype = self._chart_def.get("type")
        x = self._chart_def.get("x")
        y = self._chart_def.get("y") if ctype in ("scatter", "line") else None
        self._set_combos_silently(ctype, x, y)

        # Resetear bloque IA hasta que llegue la nueva respuesta.
        self.description_label.setText("")
        self.observations_label.setText("")
        self.exp_status_lbl.setText("Análisis de la IA")
        self.explanation_box.setVisible(False)

        self._render()
        if notify:
            self.spec_changed.emit(self)

    def _on_type_changed(self, idx: int):
        """El usuario cambia el TIPO: auto-ajustamos X/Y a columnas compatibles."""
        new_type = self.type_combo.itemData(idx)
        if not new_type:
            return
        x, y = self._current_x(), self._current_y()
        x, y = _autofix_for_type(self.df, new_type, x, y)
        if new_type in ("scatter", "line"):
            new_def = {"type": new_type, "x": x, "y": y}
        else:
            new_def = {"type": new_type, "x": x,
                       "y": "frequency" if new_type == "hist" else "count"}
        self._apply_chart_def(new_def)

    def _on_x_changed(self, x_name: str):
        if x_name not in self.df.columns:
            return
        ctype = self._current_type()
        y = self._current_y() if ctype in ("scatter", "line") else None
        # Si la combinación sigue siendo válida para el tipo actual, lo mantenemos;
        # si no, _normalize_chart_def elige el tipo más sensato para la combinación.
        new_def = _normalize_chart_def(self.df, x_name, y, preferred_type=ctype)
        self._apply_chart_def(new_def)

    def _on_y_changed(self, y_text: str):
        if y_text not in self.df.columns:
            return
        ctype = self._current_type()
        x = self._current_x()
        # Y solo se considera para tipos bidimensionales; si no, lo ignoramos
        y = y_text if ctype in ("scatter", "line") else None
        new_def = _normalize_chart_def(self.df, x, y, preferred_type=ctype)
        self._apply_chart_def(new_def)

    def _render(self):
        while self.chart_layout.count():
            item = self.chart_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        try:
            widget = create_chart_widget(self.df, self._chart_def)
            self.chart_layout.addWidget(widget)
        except Exception as e:
            err = QLabel(f"Error al pintar: {e}")
            err.setStyleSheet("color: #EF4444;")
            self.chart_layout.addWidget(err)


# ---------------------------------------------------------------------------
# Tarjeta de alternativa (sin gráfico, solo descripción)
# ---------------------------------------------------------------------------

class AlternativeCard(QFrame):
    def __init__(self, spec: dict, index: int):
        super().__init__()
        self._spec = dict(spec)
        self._index = index

        self.setObjectName("altCard")
        self.setStyleSheet(
            "QFrame#altCard {"
            "  border: 1px dashed rgba(127,127,127,0.35);"
            "  border-radius: 8px;"
            "  background: rgba(127,127,127,0.04);"
            "}"
        )
        self.setMinimumWidth(220)
        self.setMaximumWidth(260)

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(4)

        # Título con icono según tipo
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(_TYPE_ICONS.get(spec.get("type", ""), "fa5s.chart-area"),
                                    color="#818CF8").pixmap(14, 14))
        head.addWidget(icon_lbl)
        title = QLabel(f"<b>{_spec_title(spec)}</b>")
        title.setStyleSheet("font-size: 12px;")
        title.setWordWrap(True)
        head.addWidget(title, 1)
        v.addLayout(head)

        # Explicación
        explanation = spec.get("explanation", "")
        exp = QLabel(explanation if explanation else "Recomendación adicional")
        exp.setStyleSheet("color: #6B7280; font-size: 11px;")
        exp.setWordWrap(True)
        v.addWidget(exp)

    def spec(self) -> dict:
        return dict(self._spec)

    def index(self) -> int:
        return self._index


# ---------------------------------------------------------------------------
# PreviewTab
# ---------------------------------------------------------------------------

class PreviewTab(QWidget):
    """
    Pestaña Preview con gráficos recomendados.
    - Si se pasan `chart_specs` se usan; los primeros 6 son el grid principal,
      el resto van como alternativas (sin gráfico, solo descripción).
    - Si no, fallback a la heurística `select_charts`.
    """

    # Emitido cuando un panel del grid es sustituido por una alternativa
    panel_replaced = Signal(object)  # nuevo ChartPanel
    # Emitido cuando el usuario cambia X o Y dentro de un panel
    panel_spec_changed = Signal(object)  # panel

    def __init__(self, parent=None):
        super().__init__(parent)
        self.df = None
        self._ai_available = False
        self._main_specs = []   # specs renderizados en el grid principal
        self._alt_specs = []    # specs sólo como tarjeta alternativa
        self._main_panels = []  # ChartPanel actuales

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(10)

        # Cabecera
        header = QHBoxLayout()
        self.title = QLabel("<b>Vista rápida</b>")
        self.title.setStyleSheet("font-size: 20px;")
        header.addWidget(self.title)
        header.addStretch()

        self.subtitle = QLabel("")
        self.subtitle.setStyleSheet("color: #6B7280;")
        header.addWidget(self.subtitle)

        # Selector de tamaño de los gráficos. Las alturas son FIJAS (setFixedHeight)
        # del área de gráfico → la diferencia entre opciones es bien visible.
        header.addSpacing(12)
        header.addWidget(QLabel("Tamaño:"))
        self.size_combo = QComboBox()
        self.size_combo.addItem("Compacto", 200)
        self.size_combo.addItem("Normal", 320)
        self.size_combo.addItem("Grande", 460)
        self.size_combo.setCurrentIndex(1)  # Normal (mediano) por defecto
        self.size_combo.currentIndexChanged.connect(self._on_size_changed)
        header.addWidget(self.size_combo)

        self.layout.addLayout(header)

        # Mensaje de loading central
        self.loading_label = QLabel("")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("color: #6B7280; font-size: 14px; padding: 40px;")
        self.loading_label.setVisible(False)
        self.layout.addWidget(self.loading_label)

        # Grid principal envuelto en un QScrollArea: si los paneles no caben se
        # accede al resto desplazando verticalmente en vez de aplastarlos.
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(15)
        # Fila stretcher al final: absorbe el espacio sobrante para que las filas
        # con paneles se queden en su minimumHeight y el selector de tamaño funcione.
        self.grid_layout.setRowStretch(999, 1)
        self.scroll_area.setWidget(self.grid_container)
        self.layout.addWidget(self.scroll_area, 1)

        # Sección de alternativas (debajo del grid)
        self.alts_section = QWidget()
        alts_v = QVBoxLayout(self.alts_section)
        alts_v.setContentsMargins(0, 6, 0, 0)
        alts_v.setSpacing(6)
        self.alts_header = QLabel("<b>Más recomendaciones de la IA</b>  "
                                  "<span style='color:#6B7280; font-weight:normal;'>"
                                  "(pulsa el icono ⇄ de un gráfico para sustituirlo)</span>")
        self.alts_header.setStyleSheet("font-size: 13px;")
        alts_v.addWidget(self.alts_header)

        alts_scroll = QScrollArea()
        alts_scroll.setWidgetResizable(True)
        alts_scroll.setFrameShape(QFrame.NoFrame)
        alts_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        alts_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        alts_scroll.setFixedHeight(110)
        alts_inner = QWidget()
        self.alts_row = QHBoxLayout(alts_inner)
        self.alts_row.setContentsMargins(0, 0, 0, 0)
        self.alts_row.setSpacing(10)
        self.alts_row.addStretch(1)
        alts_scroll.setWidget(alts_inner)
        alts_v.addWidget(alts_scroll)
        self.layout.addWidget(self.alts_section)
        self.alts_section.setVisible(False)

        self.empty_label = QLabel("Esperando datos...")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.empty_label)

    # --- API pública -----------------------------------------------------

    def _current_chart_min_height(self) -> int:
        try:
            return int(self.size_combo.currentData())
        except Exception:
            return 320

    def _on_size_changed(self, idx: int):
        h = self.size_combo.itemData(idx) or 320
        for panel in self._main_panels:
            if panel is not None:
                try:
                    panel.set_chart_min_height(int(h))
                except RuntimeError:
                    pass

    def set_ai_available(self, available: bool):
        self._ai_available = bool(available)

    def show_loading(self, message: str):
        """Muestra un estado 'esperando IA' mientras se piden specs."""
        # Limpiar grid
        self._clear_grid()
        self._clear_alts()
        self.empty_label.hide()
        self.scroll_area.setVisible(False)
        self.alts_section.setVisible(False)
        self.subtitle.setText("")
        self.loading_label.setText(message)
        self.loading_label.setVisible(True)

    def update_data(self, df: pl.DataFrame, chart_specs: list = None,
                    source: str = "auto", on_progress=None, on_complete=None):
        """
        Renderiza los gráficos incrementalmente.
        - `chart_specs` opcional: si llega, primeros 6 van a grid; resto a alternativas.
        - `source`: "ai" | "auto" → controla subtítulo y si se muestran explicaciones.
        """
        self.df = df
        self._on_progress = on_progress
        self._on_complete = on_complete

        self.loading_label.setVisible(False)
        self._clear_grid()
        self._clear_alts()

        if df is None or df.is_empty():
            self.empty_label.setText("Esperando datos...")
            self.empty_label.show()
            self.scroll_area.setVisible(False)
            self.alts_section.setVisible(False)
            self.subtitle.setText("")
            if on_complete:
                on_complete()
            return

        self.empty_label.hide()
        self.scroll_area.setVisible(True)

        # Resolver specs (validando contra columnas existentes)
        validated = []
        if chart_specs:
            for s in chart_specs:
                if not isinstance(s, dict):
                    continue
                if s.get("x") not in df.columns:
                    continue
                validated.append(s)

        if not validated:
            # Fallback heurístico: pedimos más de 6 para que también haya
            # alternativas (swap icon) en modo auto.
            try:
                validated = select_charts(df, max_charts=10)
            except Exception:
                validated = []
            source = "auto"

        # Split: 6 principales, resto alternativas
        self._main_specs = list(validated[:6])
        self._alt_specs = list(validated[6:])
        self._source = source

        if source == "ai":
            self.subtitle.setText("Recomendado por la IA")
        else:
            self.subtitle.setText("Vista rápida automática")

        # Pintar alternativas (instantáneo, solo texto)
        self._rebuild_alts()

        # Render incremental del grid
        self._chart_index = 0
        self._row = 0
        self._col = 0
        self._main_panels = []

        if not self._main_specs:
            if on_complete:
                on_complete()
            return

        QTimer.singleShot(0, self._render_next_chart)

    # --- Render incremental ---------------------------------------------

    def _render_next_chart(self):
        if self._chart_index >= len(self._main_specs):
            # Tras renderizar todos los principales, propagar alternativas
            for panel in self._main_panels:
                panel.set_alternatives(self._alt_specs)
            if self._on_complete:
                try:
                    self._on_complete()
                except Exception:
                    pass
            return

        spec = self._main_specs[self._chart_index]
        explanation = spec.get("explanation", "") if self._source == "ai" else ""
        try:
            panel = ChartPanel(self.df, spec, self._chart_index, explanation=explanation, source=self._source)
            panel.set_chart_min_height(self._current_chart_min_height())
            panel.replace_requested.connect(self._on_replace_requested)
            panel.spec_changed.connect(self.panel_spec_changed.emit)
            self.grid_layout.addWidget(panel, self._row, self._col)
            self._main_panels.append(panel)
        except Exception as e:
            err = QLabel(f"Error en {spec.get('x','?')}: {e}")
            err.setStyleSheet("color: #EF4444;")
            self.grid_layout.addWidget(err, self._row, self._col)
            self._main_panels.append(None)

        self._col += 1
        if self._col > 1:
            self._col = 0
            self._row += 1

        self._chart_index += 1
        if self._on_progress:
            try:
                self._on_progress(self._chart_index, len(self._main_specs))
            except Exception:
                pass

        QTimer.singleShot(20, self._render_next_chart)

    # --- Swap principal <-> alternativa ----------------------------------

    def _on_replace_requested(self, panel_index: int, alt_index: int):
        if alt_index < 0 or alt_index >= len(self._alt_specs):
            return
        if panel_index < 0 or panel_index >= len(self._main_specs):
            return

        # Intercambio: el alternativo ocupa la posición, el principal pasa a alternativa
        new_spec = self._alt_specs.pop(alt_index)
        old_spec = self._main_specs[panel_index]
        self._main_specs[panel_index] = new_spec
        self._alt_specs.insert(0, old_spec)  # va al principio para que el usuario lo vea

        # Refrescar solo el panel afectado (no re-renderizamos todo)
        try:
            # Quitar el panel viejo
            old_panel = self._main_panels[panel_index]
            if old_panel is not None:
                # Calcular row/col del grid: nuestra disposición es 2 cols
                row = panel_index // 2
                col = panel_index % 2
                self.grid_layout.removeWidget(old_panel)
                old_panel.setParent(None)
                old_panel.deleteLater()

                explanation = new_spec.get("explanation", "") if self._source == "ai" else ""
                new_panel = ChartPanel(
                    self.df, new_spec, panel_index,
                    explanation=explanation, source=self._source,
                )
                new_panel.set_chart_min_height(self._current_chart_min_height())
                new_panel.replace_requested.connect(self._on_replace_requested)
                new_panel.spec_changed.connect(self.panel_spec_changed.emit)
                new_panel.set_alternatives(self._alt_specs)
                self.grid_layout.addWidget(new_panel, row, col)
                self._main_panels[panel_index] = new_panel
                # Notificar para que MainWindow pida explain_chart al panel nuevo
                self.panel_replaced.emit(new_panel)
        except Exception:
            import traceback
            traceback.print_exc()

        # Actualizar alternativas en todos los paneles principales y reconstruir la fila
        for panel in self._main_panels:
            if panel is not None:
                panel.set_alternatives(self._alt_specs)
        self._rebuild_alts()

    # --- Helpers -------------------------------------------------------

    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._main_panels = []

    def _clear_alts(self):
        # Conservamos el stretch final
        while self.alts_row.count() > 1:
            item = self.alts_row.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _rebuild_alts(self):
        self._clear_alts()
        if not self._alt_specs:
            self.alts_section.setVisible(False)
            return
        self.alts_section.setVisible(True)
        for i, spec in enumerate(self._alt_specs):
            card = AlternativeCard(spec, i)
            self.alts_row.insertWidget(self.alts_row.count() - 1, card)
