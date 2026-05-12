from PySide6.QtWidgets import (
    QMainWindow, QLabel, QVBoxLayout, QWidget, QStackedWidget, 
    QPushButton, QHBoxLayout, QProgressBar, QMessageBox, QListWidget, QListWidgetItem,
    QDialog, QComboBox
)
from PySide6.QtCore import Qt, Signal, QSize
import qtawesome as qta
from i18n.translations import tr
from settings.config import settings
from core.data_worker import DataLoaderManager, ProfilerManager
from ui.context_tab import ContextTab
from ui.preview_tab import PreviewTab
from ui.cleaning_tab import CleaningTab
from ui.advanced_tab import AdvancedTab
from ui.ai_tab import AITab
from data.ai_analyzer import AIAnalyzer

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes")
        self.resize(300, 150)
        layout = QVBoxLayout(self)
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Tema visual:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Claro", "Oscuro"])
        self.theme_combo.setCurrentIndex(0 if settings.get("theme") == "light" else 1)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(self.theme_combo)
        layout.addLayout(theme_layout)
        
        layout.addStretch()
        btn = QPushButton("Cerrar")
        btn.setObjectName("primaryBtn")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)
        
    def _on_theme_changed(self, text):
        new_theme = "light" if text == "Claro" else "dark"
        settings.set("theme", new_theme)
        from PySide6.QtWidgets import QApplication
        from ui.theme import apply_theme
        apply_theme(QApplication.instance(), new_theme)

class DragDropLabel(QLabel):
    """
    Área de arrastre que TAMBIÉN funciona como botón: al hacer clic se abre
    el selector de archivo. Sustituye al antiguo botón "Seleccionar Dataset".
    """
    file_dropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropLabel")
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(220)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragOver", True)
            self.style().unpolish(self); self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("dragOver", False)
        self.style().unpolish(self); self.style().polish(self)

    def dropEvent(self, event):
        self.setProperty("dragOver", False)
        self.style().unpolish(self); self.style().polish(self)
        urls = [url.toLocalFile() for url in event.mimeData().urls()]
        valid_files = [f for f in urls if f.lower().endswith(('.csv', '.xlsx', '.json', '.parquet'))]
        if valid_files:
            self.file_dropped.emit(valid_files)


class HomeView(QWidget):
    file_dropped = Signal(str, str)  # main_file, context_file

    def __init__(self, ai_available: bool = False, parent=None):
        super().__init__(parent)
        self.main_file = None
        self.context_file = None
        self._ai_available = ai_available

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 30, 40, 30)
        outer.setSpacing(0)
        outer.addStretch(1)

        # Bloque central, contenido reducido
        center = QVBoxLayout()
        center.setSpacing(14)
        center.setAlignment(Qt.AlignHCenter)

        # Área de arrastre (también botón). Contiene icono + texto.
        self.drop_label = DragDropLabel()
        self.drop_label.file_dropped.connect(self._on_drop)
        self.drop_label.clicked.connect(self._select_dataset)
        self.drop_label.setMaximumWidth(560)
        self.drop_label.setStyleSheet(
            "QLabel#dropLabel {"
            "  border: 2px dashed rgba(127,127,127,0.35);"
            "  border-radius: 14px;"
            "  padding: 28px 24px;"
            "  font-size: 14px;"
            "  color: #6B7280;"
            "  background: rgba(127,127,127,0.04);"
            "}"
            "QLabel#dropLabel[dragOver='true'] {"
            "  border-color: #4F46E5;"
            "  background: rgba(79,70,229,0.08);"
            "}"
        )
        center.addWidget(self.drop_label, alignment=Qt.AlignHCenter)

        # Botón secundario para diccionario (chico, debajo)
        self.browse_ctx_btn = QPushButton(qta.icon('fa5s.book', color='#6B7280'), " Añadir diccionario (opcional)")
        self.browse_ctx_btn.setObjectName("iconBtn")
        self.browse_ctx_btn.setCursor(Qt.PointingHandCursor)
        self.browse_ctx_btn.clicked.connect(self._select_context)
        center.addWidget(self.browse_ctx_btn, alignment=Qt.AlignHCenter)

        self.clear_ctx_btn = QPushButton(qta.icon('fa5s.times', color="#EF4444"), " Quitar diccionario")
        self.clear_ctx_btn.setObjectName("iconBtn")
        self.clear_ctx_btn.setCursor(Qt.PointingHandCursor)
        self.clear_ctx_btn.clicked.connect(self._clear_context)
        self.clear_ctx_btn.hide()
        center.addWidget(self.clear_ctx_btn, alignment=Qt.AlignHCenter)

        # Botón Analizar — más sobrio
        self.analyze_btn = QPushButton(qta.icon('fa5s.play', color="white"), " Analizar")
        self.analyze_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #10B981; color: white;"
            "  font-size: 13px; font-weight: 600;"
            "  padding: 9px 22px; border-radius: 6px;"
            "}"
            "QPushButton:hover { background-color: #059669; }"
            "QPushButton:disabled { background-color: rgba(127,127,127,0.25); color: rgba(255,255,255,0.6); }"
        )
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.clicked.connect(self._trigger_analysis)
        center.addSpacing(4)
        center.addWidget(self.analyze_btn, alignment=Qt.AlignHCenter)

        outer.addLayout(center)
        outer.addStretch(1)

        # Indicador de estado IA, abajo a la derecha del home view
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.addStretch(1)
        self.ai_status_label = QLabel()
        self.ai_status_label.setStyleSheet("font-size: 11px; color: #6B7280;")
        status_row.addWidget(self.ai_status_label)
        outer.addLayout(status_row)

        self._update_ui()
        self.set_ai_available(ai_available)

    # --- API pública -----------------------------------------------------

    def set_ai_available(self, available: bool):
        self._ai_available = available
        if available:
            self.ai_status_label.setText('<span style="color:#10B981;">●</span> IA disponible')
        else:
            self.ai_status_label.setText('<span style="color:#EF4444;">●</span> IA no disponible')

    def reset(self):
        self.main_file = None
        self.context_file = None
        self._update_ui()

    # --- Privado ---------------------------------------------------------

    def _update_ui(self):
        import os
        # Texto del área de drop. Mantiene la función de "click para seleccionar"
        if self.main_file:
            base = os.path.basename(self.main_file)
            text = (
                "<div style='font-size:15px;'><b>✅ Dataset:</b> " + base + "</div>"
                "<div style='font-size:11px; margin-top:6px;'>Haz clic o arrastra otro archivo para reemplazarlo.</div>"
            )
        else:
            text = (
                "<div style='font-size:24px; margin-bottom:6px;'>📂</div>"
                "<div style='font-size:15px;'><b>Arrastra un archivo</b> o haz clic para seleccionar</div>"
                "<div style='font-size:11px; margin-top:6px;'>CSV · XLSX · JSON · Parquet</div>"
            )
        self.drop_label.setText(text)

        if self.context_file:
            base = os.path.basename(self.context_file)
            self.browse_ctx_btn.hide()
            self.clear_ctx_btn.setText(f"  Quitar diccionario: {base}")
            self.clear_ctx_btn.show()
        else:
            self.browse_ctx_btn.show()
            self.clear_ctx_btn.hide()

        self.analyze_btn.setEnabled(self.main_file is not None)

    def _select_dataset(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Dataset", "",
            "Archivos Soportados (*.csv *.xlsx *.json *.parquet)"
        )
        if path:
            self.main_file = path
            self._update_ui()

    def _select_context(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Diccionario", "",
            "CSV o Texto (*.csv *.txt)"
        )
        if path:
            self.context_file = path
            self._update_ui()

    def _clear_context(self):
        self.context_file = None
        self._update_ui()

    def _on_drop(self, files: list):
        if len(files) >= 1:
            self.main_file = files[0]
        if len(files) >= 2:
            self.context_file = files[1]
        self._update_ui()

    def _trigger_analysis(self):
        if self.main_file:
            self.file_dropped.emit(self.main_file, self.context_file or "")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("app_title"))
        self.resize(1100, 768)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Backend integration (Init before UI)
        self.data_manager = DataLoaderManager()
        self.data_manager.progress_updated.connect(self._update_progress, Qt.QueuedConnection)
        self.data_manager.dataset_loaded.connect(self._on_dataset_loaded, Qt.QueuedConnection)
        self.data_manager.error_occurred.connect(self._on_load_error, Qt.QueuedConnection)
        
        self.profiler_manager = ProfilerManager()
        self.profiler_manager.profile_ready.connect(self._on_profile_ready, Qt.QueuedConnection)
        self.profiler_manager.error_occurred.connect(self._on_load_error, Qt.QueuedConnection)
        
        self.ai_analyzer = AIAnalyzer(model="qwen3:30b")
        self.ai_available = self.ai_analyzer.check_connection()

        if self.ai_available:
            self.ai_analyzer.chunk_received.connect(self._on_ai_chunk, Qt.QueuedConnection)
            self.ai_analyzer.report_ready.connect(self._on_ai_ready, Qt.QueuedConnection)
            self.ai_analyzer.error_occurred.connect(self._on_ai_error, Qt.QueuedConnection)
            # Recomendaciones de gráficos
            self.ai_analyzer.charts_recommended.connect(self._on_ai_charts_recommended, Qt.QueuedConnection)
            self.ai_analyzer.charts_error.connect(self._on_ai_charts_error, Qt.QueuedConnection)
            # Explicación de gráficos del Avanzado
            self.ai_analyzer.chart_explanation_ready.connect(self._on_chart_explanation_ready, Qt.QueuedConnection)
            self.ai_analyzer.chart_explanation_error.connect(self._on_chart_explanation_error, Qt.QueuedConnection)
            # Recomendaciones de limpieza por IA
            self.ai_analyzer.cleaning_recommendations_ready.connect(self._on_ai_cleaning_ready, Qt.QueuedConnection)
            self.ai_analyzer.cleaning_recommendations_error.connect(self._on_ai_cleaning_error, Qt.QueuedConnection)
        
        self._setup_topbar()
        
        # Main Body (Sidebar + Content)
        self.body_widget = QWidget()
        self.body_layout = QHBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        
        self._setup_sidebar()
        
        # Content Area Stack
        self.content_stack = QStackedWidget()
        self.body_layout.addWidget(self.content_stack, 1)
        
        self.main_layout.addWidget(self.body_widget, 1)

        # Views inside the stack
        self.home_view = HomeView(ai_available=self.ai_available)
        self.home_view.file_dropped.connect(self._on_file_dropped)
        self.content_stack.addWidget(self.home_view)

        self._setup_progress_ui()
        self._setup_tabs()

        # Initially hide sidebar
        self.sidebar_container.hide()

    def _setup_topbar(self):
        self.topbar = QWidget()
        self.topbar.setObjectName("topbar")
        self.topbar.setFixedHeight(50)
        
        top_layout = QHBoxLayout(self.topbar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        
        # Title
        title_lbl = QLabel(f"<b>{tr('app_title')}</b>")
        title_lbl.setStyleSheet("font-size: 16px;")
        top_layout.addWidget(title_lbl)
        
        top_layout.addSpacing(20)
        
        # File info
        self.file_label = QLabel("")
        self.file_label.setStyleSheet("color: #6B7280;")
        top_layout.addWidget(self.file_label)
        
        top_layout.addStretch()
        
        # Action Buttons
        self.close_file_btn = QPushButton(qta.icon('fa5s.times-circle', color='#6B7280'), "Cerrar archivo")
        self.close_file_btn.setObjectName("iconBtn")
        self.close_file_btn.hide()
        self.close_file_btn.clicked.connect(self._on_close_file)
        top_layout.addWidget(self.close_file_btn)
        
        self.settings_btn = QPushButton(qta.icon('fa5s.cog', color='#6B7280'), "")
        self.settings_btn.setObjectName("iconBtn")
        self.settings_btn.clicked.connect(self._show_settings)
        top_layout.addWidget(self.settings_btn)
        
        self.main_layout.addWidget(self.topbar)

    def _setup_sidebar(self):
        self.sidebar_container = QWidget()
        self.sidebar_container.setObjectName("sidebar")
        self.sidebar_container.setFixedWidth(220)
        
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 10, 0, 10)
        
        self.sidebar_list = QListWidget()
        self.sidebar_list.setObjectName("sidebarList")
        self.sidebar_list.setSpacing(2)
        
        # Items (Contexto y Limpieza primero, antes de que aparezcan los gráficos)
        items_data = [
            ("Contexto", 'fa5s.database'),
            ("Limpieza", 'fa5s.broom'),
            ("Preview", 'fa5s.chart-pie'),
            ("Custom", 'fa5s.sliders-h'),
        ]

        if self.ai_available:
            items_data.append(("Asistente IA", 'fa5s.robot'))
        
        color = "#818CF8" if settings.get("theme") == "dark" else "#4F46E5"
        
        for text, icon_name in items_data:
            item = QListWidgetItem(qta.icon(icon_name, color=color), text)
            self.sidebar_list.addItem(item)
            
        self.sidebar_list.currentRowChanged.connect(self._on_sidebar_changed)
        sidebar_layout.addWidget(self.sidebar_list)
        
        self.body_layout.addWidget(self.sidebar_container)

    def _setup_tabs(self):
        # We store the tabs in a QStackedWidget managed by the sidebar
        self.tabs_stack = QStackedWidget()

        self.preview_tab = PreviewTab()
        self.preview_tab.set_ai_available(self.ai_available)
        self.preview_tab.panel_replaced.connect(self._on_preview_panel_replaced)
        self.preview_tab.panel_spec_changed.connect(self._on_preview_panel_replaced)
        self.advanced_tab = AdvancedTab()
        self.advanced_tab.set_ai_available(self.ai_available)
        self.advanced_tab.explain_requested.connect(self._on_advanced_explain_requested)
        self.cleaning_tab = CleaningTab()
        self.context_tab = ContextTab()
        
        # Mismo orden que el sidebar: Contexto, Limpieza, Preview, Custom
        self.tabs_stack.addWidget(self.context_tab)
        self.tabs_stack.addWidget(self.cleaning_tab)
        self.tabs_stack.addWidget(self.preview_tab)
        self.tabs_stack.addWidget(self.advanced_tab)
        
        if self.ai_available:
            self.ai_tab = AITab()
            self.ai_tab.send_message.connect(self.ai_analyzer.send_chat_message)
            self.tabs_stack.addWidget(self.ai_tab)
        
        self.content_stack.addWidget(self.tabs_stack)

    def _setup_progress_ui(self):
        self.progress_container = QWidget()
        layout = QVBoxLayout(self.progress_container)
        layout.setAlignment(Qt.AlignCenter)
        
        inner_container = QWidget()
        inner_layout = QVBoxLayout(inner_container)
        inner_container.setMaximumWidth(400)
        
        self.progress_label = QLabel(tr("loading"))
        self.progress_label.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        inner_layout.addWidget(self.progress_bar)
        
        layout.addWidget(inner_container)
        self.content_stack.addWidget(self.progress_container)

    def _show_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def _on_sidebar_changed(self, index: int):
        self.tabs_stack.setCurrentIndex(index)

    def _on_file_dropped(self, file_path: str, context_path: str):
        import os
        filename = os.path.basename(file_path)
        self.file_label.setText(filename)
        self.current_context_path = context_path
        
        self.content_stack.setCurrentWidget(self.progress_container)
        self.progress_label.setText("Analizando archivo...")
        self.progress_bar.setValue(0)
        self.data_manager.load_file(file_path)

    def _update_progress(self, percentage: float, time_str: str):
        self.progress_bar.setValue(int(percentage))
        self.progress_label.setText(f"Cargando... {int(percentage)}% (Est: {time_str})")

    def _on_dataset_loaded(self, df):
        # We don't switch tabs yet. We keep the progress bar visible.
        self.progress_bar.setValue(50)
        self.progress_label.setText("Analizando perfil del dataset...")
        
        # Save df reference to update tabs later
        self._current_df = df
        
        # Start profiling in background
        self.profiler_manager.run_profile(df)
        
    def _on_profile_ready(self, profile: dict, recs: list):
        """
        Nuevo flujo no-bloqueante:
        1. Actualizar pestañas rápidas (Contexto, Limpieza, combos de Avanzado).
        2. Cambiar a la vista de tabs YA con Preview en estado de loading.
        3. Lanzar la petición de recomendaciones a la IA en background.
        4. Cuando llegue (o salte el timeout/error), renderizar Preview en sitio.
        """
        self._pending_profile = profile
        # Resetear rutas de explain (las respuestas viejas se descartan al no
        # encontrar el panel destruido, pero limpiar evita el leak).
        self._explain_routes = {}

        # Pestañas ligeras
        try:
            self.context_tab.update_profile(profile, context_text=self._read_context_text())
            self.cleaning_tab.update_recommendations(recs)
        except Exception:
            import traceback
            traceback.print_exc()

        # Lanzar petición a la IA para detectar problemas de limpieza adicionales
        if self.ai_available:
            try:
                samples = {c.get("name"): c.get("samples", []) for c in profile.get("columns", [])}
                self.cleaning_tab.set_ai_loading(True)
                self.ai_analyzer.recommend_cleaning(profile, samples, self._read_context_text())
            except Exception:
                import traceback
                traceback.print_exc()

        # Combos del Avanzado (sin renderizar gráfico aún; lazy)
        try:
            if hasattr(self, "_current_df") and self._current_df is not None:
                self.advanced_tab.update_data(self._current_df)
        except Exception:
            import traceback
            traceback.print_exc()

        # Preview en estado loading
        if self.ai_available:
            self.preview_tab.show_loading(
                "Pidiendo recomendaciones a la IA…\n\n"
                "Mientras tanto, puedes echar un ojo al Contexto, Limpieza o Avanzado."
            )
        else:
            self.preview_tab.show_loading("Generando vista automática…")

        # Cambio a tabs YA (el usuario ya puede navegar)
        self.progress_bar.setValue(100)
        self._show_tabs_after_load()

        # Iniciar petición de gráficos en background
        self._ai_charts_received = False
        self._ai_charts_specs = None
        from PySide6.QtCore import QTimer

        if self.ai_available:
            try:
                self.ai_analyzer.recommend_charts(profile, self._read_context_text(), count=10)
            except Exception:
                import traceback
                traceback.print_exc()
                self._ai_charts_received = True
                QTimer.singleShot(20, self._render_preview_charts)

            # Watchdog: si la IA tarda más de 5 minutos en devolver las
            # recomendaciones de gráficos, caemos a la heurística.
            QTimer.singleShot(300000, self._chart_recommendations_timeout)
        else:
            # Sin IA: render automático con la heurística inmediato
            QTimer.singleShot(50, self._render_preview_charts)

    def _render_preview_charts(self):
        """Renderiza el grid del Preview con los specs disponibles (o fallback)."""
        if not hasattr(self, "_current_df") or self._current_df is None:
            return
        df = self._current_df
        specs = self._ai_charts_specs
        source = "ai" if specs else "auto"
        try:
            self.preview_tab.update_data(
                df,
                chart_specs=specs,
                source=source,
                on_complete=self._request_preview_explanations,
            )
        except Exception:
            import traceback
            traceback.print_exc()

    def _request_preview_explanations(self):
        """Tras renderizar Preview, pedir explain_chart por cada panel principal."""
        if not self.ai_available or not hasattr(self, "_pending_profile"):
            return
        if not getattr(self, "_explain_routes", None):
            self._explain_routes = {}
        for panel in self.preview_tab._main_panels:
            if panel is None:
                continue
            self._request_explain_for_panel(panel)

    def _on_preview_panel_replaced(self, panel):
        """Tras un swap principal↔alternativa, pedir explain para el panel nuevo."""
        if panel is None:
            return
        self._request_explain_for_panel(panel)

    def _request_explain_for_panel(self, panel):
        if not self.ai_available or not hasattr(self, "_pending_profile"):
            return
        if not getattr(self, "_explain_routes", None):
            self._explain_routes = {}
        try:
            panel.show_observations_loading()
        except Exception:
            pass

        # request_id incremental: si el usuario cambia varias veces seguidas,
        # las respuestas viejas no encontrarán su id en las rutas y se descartan.
        seq = getattr(panel, "_explain_seq", 0) + 1
        panel._explain_seq = seq
        # Limpiar rutas viejas asociadas al mismo panel
        for k in [k for k, v in self._explain_routes.items() if v is panel]:
            self._explain_routes.pop(k, None)
        req_id = f"preview:{id(panel)}:{seq}"
        self._explain_routes[req_id] = panel

        try:
            self.ai_analyzer.explain_chart(
                panel.current_spec(),
                self._pending_profile,
                self._read_context_text(),
                request_id=req_id,
            )
        except Exception:
            import traceback
            traceback.print_exc()

    def _on_ai_charts_recommended(self, specs: list):
        if self._ai_charts_received:
            return
        self._ai_charts_received = True
        self._ai_charts_specs = specs if specs else None
        self._render_preview_charts()

    def _on_ai_charts_error(self, error_msg: str):
        if self._ai_charts_received:
            return
        self._ai_charts_received = True
        self._ai_charts_specs = None
        self.preview_tab.show_loading(
            "La IA no devolvió recomendaciones, usando vista automática…"
        )
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._render_preview_charts)

    def _chart_recommendations_timeout(self):
        if self._ai_charts_received:
            return
        self._ai_charts_received = True
        self._ai_charts_specs = None
        self.preview_tab.show_loading("La IA tardó demasiado, usando vista automática…")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._render_preview_charts)

    def _on_advanced_explain_requested(self, chart_def: dict):
        """Pide a la IA un análisis del gráfico de Custom que se acaba de renderizar."""
        if not self.ai_available or not hasattr(self, "_pending_profile"):
            return
        try:
            self.ai_analyzer.explain_chart(
                chart_def,
                self._pending_profile,
                self._read_context_text(),
                request_id="custom",
            )
        except Exception:
            import traceback
            traceback.print_exc()

    def _on_chart_explanation_ready(self, request_id: str, description: str, observations: str):
        # Ruta hacia el panel del Preview si el id está registrado
        routes = getattr(self, "_explain_routes", {}) or {}
        if request_id and request_id in routes:
            panel = routes.pop(request_id, None)
            if panel is not None:
                try:
                    panel.set_ai_observations(observations, description=description)
                except RuntimeError:
                    # El panel fue destruido (p.ej. swap o nueva carga)
                    pass
                except Exception:
                    import traceback
                    traceback.print_exc()
            return
        # Por defecto va al Custom (id "custom" o vacío)
        try:
            self.advanced_tab.show_ai_explanation(description, observations)
        except Exception:
            import traceback
            traceback.print_exc()

    def _on_ai_cleaning_ready(self, ai_recs: list):
        try:
            self.cleaning_tab.set_ai_recommendations(ai_recs or [])
        except Exception:
            import traceback
            traceback.print_exc()

    def _on_ai_cleaning_error(self, error_msg: str):
        try:
            self.cleaning_tab.set_ai_error(error_msg)
        except Exception:
            pass

    def _on_chart_explanation_error(self, request_id: str, error_msg: str):
        routes = getattr(self, "_explain_routes", {}) or {}
        if request_id and request_id in routes:
            panel = routes.pop(request_id, None)
            if panel is not None:
                try:
                    panel.set_ai_error()
                except Exception:
                    pass
            return
        try:
            self.advanced_tab.show_ai_error(error_msg)
        except Exception:
            pass

    def _read_context_text(self) -> str:
        try:
            path = getattr(self, "current_context_path", "") or ""
            if path:
                import os
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
        except Exception:
            pass
        return ""

    def _show_tabs_after_load(self):
        self.progress_bar.setValue(100)

        # Recién ahora cambiamos a la vista de pestañas: todo está renderizado
        self.content_stack.setCurrentWidget(self.tabs_stack)
        self.sidebar_container.show()
        self.close_file_btn.show()
        self.sidebar_list.setCurrentRow(0)

        # Lanzar la IA después del cambio para no añadir más carga al hilo principal
        if self.ai_available and hasattr(self, '_pending_profile'):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(150, self._start_ai_generation)

    def _start_ai_generation(self):
        try:
            profile = getattr(self, '_pending_profile', {}) or {}
            context_text = self._read_context_text()

            self.ai_tab.reset()
            self.ai_tab.set_status("Analizando datos...")
            self.ai_analyzer.generate_initial_report(profile, context_text)
        except Exception:
            import traceback
            traceback.print_exc()
        
    def _on_ai_chunk(self, chunk: str):
        self.ai_tab.append_chunk(chunk)

    def _on_ai_ready(self, full_text: str):
        # Forzar render final del markdown acumulado y marcar como listo.
        try:
            self.ai_tab.flush()
        except Exception:
            pass
        self.ai_tab.set_status("Listo")
        
    def _on_ai_error(self, error_msg: str):
        self.ai_tab.set_error(error_msg)
        
    def _on_load_error(self, error_msg: str):
        self.content_stack.setCurrentWidget(self.home_view)
        QMessageBox.critical(self, tr("error"), error_msg)
        
    def _on_close_file(self):
        # Reset view
        self.sidebar_container.hide()
        self.close_file_btn.hide()
        self.file_label.setText("")
        self.home_view.reset()
        self.content_stack.setCurrentWidget(self.home_view)
