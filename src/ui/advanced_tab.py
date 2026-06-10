import polars as pl
import threading
import traceback
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QFrame
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QColor
import qtawesome as qta
from settings.config import settings

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False


if WEBENGINE_AVAILABLE:
    class SilentWebPage(QWebEnginePage):
        """
        Página de WebEngine que NUNCA abre ventanas nuevas ni muestra diálogos JS.
        El gráfico de Plotly puede llamar a window.open() / alert() / confirm() en
        ciertos casos y eso provoca un popup/ventana extra (el bug que veía el
        usuario al abrir Custom por primera vez).
        """

        def createWindow(self, _type):
            return None

        def javaScriptAlert(self, securityOrigin, msg):
            return

        def javaScriptConfirm(self, securityOrigin, msg):
            return False

        def javaScriptPrompt(self, securityOrigin, msg, defaultValue):
            return False, ""


def _loading_html(theme: str) -> str:
    bg = "#1E1E1E" if theme == "dark" else "#FFFFFF"
    fg = "#E5E7EB" if theme == "dark" else "#1F2937"
    accent = "#818CF8" if theme == "dark" else "#4F46E5"
    return f"""
    <html><head><meta charset='utf-8'><style>
      html,body{{height:100%;margin:0;background:{bg};color:{fg};font-family:Segoe UI,Arial,sans-serif;}}
      .wrap{{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;}}
      .spinner{{width:48px;height:48px;border:4px solid rgba(127,127,127,0.25);border-top-color:{accent};
        border-radius:50%;animation:spin 1s linear infinite;margin-bottom:18px;}}
      @keyframes spin{{to{{transform:rotate(360deg);}}}}
      .msg{{font-size:15px;opacity:0.85;}}
    </style></head><body>
      <div class='wrap'><div class='spinner'></div><div class='msg'>Generando gráfico…</div></div>
    </body></html>
    """

class AdvancedTab(QWidget):
    # Señales para entregar el resultado del render desde el hilo de fondo al hilo de UI
    _plot_ready = Signal(str)   # ruta al HTML generado
    _plot_error = Signal(str)   # mensaje de error

    # MainWindow se conecta a esta señal para pedir explicación a la IA
    explain_requested = Signal(dict)  # chart_def normalizado

    def __init__(self, parent=None):
        super().__init__(parent)
        self.df = None
        self._render_thread = None
        self._render_busy = False
        self._ai_available = False
        self._last_chart_def = None
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.controls_widget = QWidget()
        self.controls_widget.setFixedWidth(260)
        self.controls_widget.setObjectName("sidebar")
        
        self.controls_layout = QVBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(25, 25, 25, 25)
        self.controls_layout.setSpacing(20)
        
        title = QLabel("<b>Panel de Exploración</b>")
        title.setStyleSheet("font-size: 18px; margin-bottom: 5px;")
        self.controls_layout.addWidget(title)
        
        self.controls_layout.addWidget(QLabel("Tipo de Gráfico"))
        self.type_combo = QComboBox()
        
        types = [
            ("Dispersión (Scatter)", 'fa5s.braille'),
            ("Línea", 'fa5s.chart-line'),
            ("Barras", 'fa5s.chart-bar'),
            ("Histograma", 'fa5s.align-left'),
            ("Cajas (Boxplot)", 'fa5s.box'),
            ("Correlación (Heatmap)", 'fa5s.th')
        ]
        color = "#818CF8" if settings.get("theme") == "dark" else "#4F46E5"
        for text, icon in types:
            self.type_combo.addItem(qta.icon(icon, color=color), text)
            
        from PySide6.QtCore import QSize
        self.type_combo.setIconSize(QSize(20, 20))
            
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        self.controls_layout.addWidget(self.type_combo)
        
        self.x_label = QLabel("Eje X")
        self.controls_layout.addWidget(self.x_label)
        self.x_combo = QComboBox()
        self.controls_layout.addWidget(self.x_combo)
        
        self.y_label = QLabel("Eje Y / Valor")
        self.controls_layout.addWidget(self.y_label)
        self.y_combo = QComboBox()
        self.controls_layout.addWidget(self.y_combo)
        
        self.controls_layout.addStretch()
        
        self.render_btn = QPushButton(qta.icon('fa5s.paint-brush', color='white'), " Renderizar")
        self.render_btn.setObjectName("primaryBtn")
        self.render_btn.clicked.connect(self._render_plot)
        self.controls_layout.addWidget(self.render_btn)
        
        self.layout.addWidget(self.controls_widget)

        self.plot_area = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_area)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        if WEBENGINE_AVAILABLE:
            self.webview = QWebEngineView()
            # Sustituir la QWebEnginePage por una que NO abra ventanas nuevas ni
            # muestre diálogos JS. Esto evita el popup que aparecía al abrir Custom.
            try:
                silent_page = SilentWebPage(self.webview)
                self.webview.setPage(silent_page)
            except Exception:
                pass
            # Desactivar también la capacidad de window.open desde JS.
            try:
                s = self.webview.settings()
                s.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
                s.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, False)
                s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
            except Exception:
                pass
            # Fijar el color de fondo de la página del WebEngine al tema actual,
            # para que no aparezca un cuadrado blanco mientras (o después de) cargar.
            try:
                _theme = settings.get("theme")
                _bg = "#1E1E1E" if _theme == "dark" else "#FFFFFF"
                self.webview.page().setBackgroundColor(QColor(_bg))
            except Exception:
                pass
            self.plot_layout.addWidget(self.webview, 1)
        else:
            self.plot_layout.addWidget(QLabel("QWebEngineView no está disponible."), 1)

        # Bloque con el análisis de la IA debajo del gráfico (theme-aware)
        if settings.get("theme") == "dark":
            _accent = "#A5B4FC"
            _desc_color = "#C7D2FE"
            _obs_color = "#E5E7EB"
        else:
            _accent = "#4F46E5"
            _desc_color = "#4338CA"
            _obs_color = "#1F2937"

        self.ai_block = QFrame()
        self.ai_block.setObjectName("aiBlock")
        self.ai_block.setStyleSheet(
            "QFrame#aiBlock {"
            "  border: 1px solid rgba(79,70,229,0.22);"
            f"  border-left: 3px solid {_accent};"
            "  border-radius: 8px;"
            "  background: rgba(79,70,229,0.06);"
            "}"
        )
        ai_v = QVBoxLayout(self.ai_block)
        ai_v.setContentsMargins(12, 8, 12, 10)
        ai_v.setSpacing(6)

        ai_head = QHBoxLayout()
        ai_head.setContentsMargins(0, 0, 0, 0)
        ai_icon = QLabel()
        ai_icon.setPixmap(qta.icon("fa5s.robot", color=_accent).pixmap(13, 13))
        ai_head.addWidget(ai_icon)
        self.ai_status_lbl = QLabel("Análisis de la IA")
        self.ai_status_lbl.setStyleSheet(
            f"font-size: 12px; color: {_accent}; font-weight: 600; background: transparent;"
        )
        ai_head.addWidget(self.ai_status_lbl)
        ai_head.addStretch(1)
        ai_v.addLayout(ai_head)

        self.ai_description_lbl = QLabel("")
        self.ai_description_lbl.setWordWrap(True)
        self.ai_description_lbl.setStyleSheet(
            f"font-size: 12px; font-style: italic; color: {_desc_color}; background: transparent;"
        )
        ai_v.addWidget(self.ai_description_lbl)

        self.ai_observations_lbl = QLabel("")
        self.ai_observations_lbl.setWordWrap(True)
        self.ai_observations_lbl.setStyleSheet(
            f"font-size: 13px; padding-top: 2px; color: {_obs_color}; background: transparent;"
        )
        ai_v.addWidget(self.ai_observations_lbl)

        self.ai_block.setMaximumHeight(190)
        self.ai_block.setVisible(False)
        self.plot_layout.addWidget(self.ai_block)

        self.layout.addWidget(self.plot_area, 1)

        # Cross-thread signals → ejecutar en hilo de UI cuando el thread termine
        self._plot_ready.connect(self._on_plot_ready, Qt.QueuedConnection)
        self._plot_error.connect(self._on_plot_error, Qt.QueuedConnection)

    def _on_type_changed(self, text):
        # Desactivar el eje Y para Histograma o Heatmap si hace falta
        if text in ["Histograma", "Barras"]:
            self.y_combo.setEnabled(False)
        else:
            self.y_combo.setEnabled(True)

    def update_data(self, df: pl.DataFrame):
        self.df = df
        if df is None or df.is_empty():
            return

        cols = df.columns

        # bloquear señales para no renderizar mientras se rellena
        self.x_combo.blockSignals(True)
        self.y_combo.blockSignals(True)

        self.x_combo.clear()
        self.y_combo.clear()

        self.x_combo.addItems(cols)
        self.y_combo.addItems(cols)

        num_cols = [c for c in cols if df[c].dtype in pl.NUMERIC_DTYPES]
        if len(num_cols) >= 2:
            self.x_combo.setCurrentText(num_cols[0])
            self.y_combo.setCurrentText(num_cols[1])

        self.x_combo.blockSignals(False)
        self.y_combo.blockSignals(False)

        # NO renderizamos aquí: cargar Plotly+WebEngine durante la carga inicial
        # del dataset (mientras también arranca el streaming de la IA) congela
        # la UI. Marcamos render pendiente y lo disparamos cuando el usuario
        # abra esta pestaña por primera vez (showEvent) o pulse "Renderizar".
        self._needs_render = True

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_needs_render", False) and self.df is not None:
            self._needs_render = False
            from PySide6.QtCore import QTimer
            # Pequeño delay para que la pestaña termine de mostrarse antes
            # de empezar el trabajo pesado de Plotly + WebEngine.
            QTimer.singleShot(100, self._render_plot)

    def _render_plot(self):
        """
        Lanza la generación del gráfico en un hilo de fondo. La UI se mantiene
        responsiva mostrando un loading dentro del WebEngine. Cuando el HTML
        está listo, se carga vía señal en el hilo de UI.
        """
        if not WEBENGINE_AVAILABLE or self.df is None:
            return

        # Evitar lanzar múltiples renders en paralelo
        if self._render_busy:
            return
        self._render_busy = True
        self.render_btn.setEnabled(False)

        # Capturar parámetros y tema en el hilo de UI (no tocar widgets desde el thread)
        gtype = self.type_combo.currentText()
        x = self.x_combo.currentText()
        y = self.y_combo.currentText()
        theme = settings.get("theme")
        df = self.df  # referencia inmutable para el thread

        # Guardar el chart_def actual para que MainWindow pueda pedir análisis IA
        self._last_chart_def = {"type": gtype, "x": x, "y": y}

        # Mostrar loading inmediatamente
        try:
            self.webview.setHtml(_loading_html(theme))
        except Exception:
            pass

        self._render_thread = threading.Thread(
            target=self._build_plot_in_thread,
            args=(df, gtype, x, y, theme),
            daemon=True,
        )
        self._render_thread.start()

    def _build_plot_in_thread(self, df, gtype, x, y, theme):
        try:
            import plotly.express as px
            import tempfile
            import os

            template = "plotly_dark" if theme == "dark" else "plotly_white"

            if gtype == "Correlación (Heatmap)":
                num_cols = [c for c in df.columns if df[c].dtype in pl.NUMERIC_DTYPES]
                df_pd = df.select(num_cols).drop_nulls().head(5000).to_pandas()
                fig = px.imshow(df_pd.corr(), text_auto=True, title="Matriz de Correlación", template=template)
            else:
                cols_to_select = [x] if gtype in ["Histograma", "Barras"] else [x, y]
                cols_to_select = list(dict.fromkeys(cols_to_select))
                df_pd = df.select(cols_to_select).drop_nulls().head(10000).to_pandas()

                if gtype == "Dispersión (Scatter)":
                    # render_mode='svg' evita WebGL (no disponible porque
                    # QTWEBENGINE_CHROMIUM_FLAGS lleva --disable-gpu).
                    fig = px.scatter(df_pd, x=x, y=y, title=f"{x} vs {y}", template=template, render_mode='svg')
                elif gtype == "Línea":
                    fig = px.line(df_pd.sort_values(x), x=x, y=y, title=f"Evolución de {y} por {x}", template=template, render_mode='svg')
                elif gtype == "Barras":
                    counts = df_pd[x].value_counts().reset_index().head(20)
                    counts.columns = [x, 'count']
                    fig = px.bar(counts, x=x, y='count', title=f"Top 20 Frecuencias de {x}", template=template)
                elif gtype == "Histograma":
                    fig = px.histogram(df_pd, x=x, title=f"Distribución de {x}", template=template)
                elif gtype == "Cajas (Boxplot)":
                    fig = px.box(df_pd, x=x, y=y, title=f"Distribución de {y} por {x}", template=template)
                else:
                    self._plot_error.emit(f"Tipo de gráfico no soportado: {gtype}")
                    return

            font_color = "#E5E7EB" if theme == "dark" else "#1F2937"
            bg_color = "#1E1E1E" if theme == "dark" else "#FFFFFF"
            grid_color = "rgba(255,255,255,0.1)" if theme == "dark" else "rgba(0,0,0,0.1)"

            fig.update_layout(
                paper_bgcolor=bg_color,
                plot_bgcolor=bg_color,
                font=dict(color=font_color),
                xaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color),
                yaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color),
            )

            # Embebemos plotly.js dentro del HTML (en vez de cargarlo de CDN) para
            # que funcione aunque el QWebEngineView no tenga acceso a internet.
            # El HTML pesa más, pero se renderiza siempre.
            html = fig.to_html(include_plotlyjs=True)

            # Plotly genera un HTML con body sin estilos → sale un cuadrado blanco
            # alrededor del gráfico aunque el paper_bgcolor sea del tema.
            # Inyectamos CSS para que html/body cojan el color del tema.
            theme_css = (
                f"<style>html,body{{background:{bg_color} !important;"
                f"margin:0;padding:0;color:{font_color};}}"
                f".plotly-graph-div{{background:{bg_color} !important;}}</style>"
            )
            if "<head>" in html:
                html = html.replace("<head>", "<head>" + theme_css, 1)
            else:
                html = theme_css + html

            tmp_path = os.path.join(tempfile.gettempdir(), "datapreview_plot.html")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(html)

            self._plot_ready.emit(tmp_path)
        except Exception as e:
            traceback.print_exc()
            self._plot_error.emit(str(e))

    def _on_plot_ready(self, path: str):
        try:
            self.webview.setUrl(QUrl.fromLocalFile(path))
        except Exception:
            traceback.print_exc()
        finally:
            self._render_busy = False
            self.render_btn.setEnabled(True)

        # Pedir análisis a la IA (si está disponible) con el chart_def actual
        if self._ai_available and self._last_chart_def:
            self._show_ai_loading()
            try:
                self.explain_requested.emit(dict(self._last_chart_def))
            except Exception:
                traceback.print_exc()

    def _on_plot_error(self, error_msg: str):
        try:
            self.webview.setHtml(
                f"<h3 style='color:#EF4444; font-family:sans-serif; padding:20px;'>Error al renderizar: {error_msg}</h3>"
            )
        except Exception:
            pass
        self._render_busy = False
        self.render_btn.setEnabled(True)
        # Ocultar bloque de IA si hubo error
        self.ai_block.setVisible(False)

    # --- Análisis IA ----------------------------------------------------

    def set_ai_available(self, available: bool):
        self._ai_available = bool(available)
        if not self._ai_available:
            self.ai_block.setVisible(False)

    def _show_ai_loading(self):
        self.ai_status_lbl.setText("Analizando con IA...")
        self.ai_description_lbl.setText("")
        self.ai_observations_lbl.setText("La IA está revisando el gráfico, un momento...")
        self.ai_block.setVisible(True)

    def show_ai_explanation(self, description: str, observations: str):
        self.ai_status_lbl.setText("Análisis de la IA")
        self.ai_description_lbl.setText(description or "")
        self.ai_observations_lbl.setText(observations or "")
        self.ai_block.setVisible(bool(description or observations))

    def show_ai_error(self, error_msg: str):
        # Ocultamos directamente para no ensuciar; opcionalmente podríamos mostrar el error
        self.ai_block.setVisible(False)
