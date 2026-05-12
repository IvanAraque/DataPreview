from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QLineEdit, QPushButton, QLabel, QScrollArea
from PySide6.QtCore import Qt, Signal, QTimer
import qtawesome as qta
from settings.config import settings

class AITab(QWidget):
    send_message = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        self.title = QLabel("Asistente IA")
        self.title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(self.title)
        
        self.status_label = QLabel("Esperando datos...")
        self.status_label.setStyleSheet("color: #6B7280;")
        header_layout.addWidget(self.status_label, alignment=Qt.AlignRight)
        self.layout.addLayout(header_layout)
        
        # Chat / Report Area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                font-size: 14px;
                line-height: 1.55;
                padding: 14px 16px;
                border: 1px solid rgba(127,127,127,0.25);
                border-radius: 10px;
                background: rgba(127,127,127,0.04);
            }
        """)

        # CSS sobre el documento HTML para que el markdown se vea con jerarquia:
        # titulos en color de acento, strong/keywords destacados, code con fondo,
        # blockquote con barra lateral, párrafos separados.
        accent = "#818CF8" if settings.get("theme") == "dark" else "#4F46E5"
        accent_soft = "rgba(79,70,229,0.12)" if settings.get("theme") != "dark" else "rgba(129,140,248,0.16)"
        self.chat_display.document().setDefaultStyleSheet(f"""
            h1 {{ color: {accent}; font-size: 19px; margin: 14px 0 8px 0; }}
            h2 {{ color: {accent}; font-size: 16px; margin: 12px 0 6px 0;
                  border-bottom: 1px solid {accent_soft}; padding-bottom: 2px; }}
            h3 {{ color: {accent}; font-size: 14px; margin: 10px 0 4px 0; }}
            h4, h5, h6 {{ color: {accent}; font-size: 13px; margin: 8px 0 4px 0; }}
            p  {{ margin: 8px 0; }}
            ul, ol {{ margin: 6px 0 6px 18px; }}
            li {{ margin: 2px 0; }}
            strong, b {{ color: {accent}; }}
            em, i {{ font-style: italic; }}
            code {{ background: {accent_soft}; padding: 1px 4px; border-radius: 3px;
                    font-family: Consolas, Menlo, monospace; font-size: 13px; }}
            pre {{ background: {accent_soft}; padding: 8px 10px; border-radius: 6px;
                   font-family: Consolas, Menlo, monospace; font-size: 13px; }}
            blockquote {{ border-left: 3px solid {accent}; padding: 4px 10px;
                          margin: 8px 0; background: {accent_soft}; }}
            hr {{ border: 0; border-top: 1px solid {accent_soft}; margin: 10px 0; }}
            a {{ color: {accent}; }}
        """)

        self.layout.addWidget(self.chat_display, 1)
        
        # Input Area
        self.input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Pregunta algo a la IA sobre los datos...")
        self.input_field.returnPressed.connect(self._on_send)
        self.input_layout.addWidget(self.input_field, 1)
        
        self.send_btn = QPushButton(qta.icon('fa5s.paper-plane', color='white'), "Enviar")
        self.send_btn.setObjectName("primaryBtn")
        self.send_btn.clicked.connect(self._on_send)
        self.input_layout.addWidget(self.send_btn)
        
        self.layout.addLayout(self.input_layout)

        self._current_content = ""

        # Throttle de actualizaciones del markdown: en lugar de re-parsear todo
        # el markdown por cada chunk de la IA (que freezea la UI con respuestas
        # largas), agrupamos los chunks y refrescamos cada ~150ms.
        self._pending_flush = False
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(150)
        self._flush_timer.timeout.connect(self._flush_markdown)

    def set_status(self, text: str, is_error: bool = False):
        self.status_label.setText(text)
        if is_error:
            self.status_label.setStyleSheet("color: #EF4444;") # Red
        else:
            self.status_label.setStyleSheet("color: #10B981;") # Green

    def append_chunk(self, chunk: str):
        # Acumulamos siempre, pero el repintado va por timer.
        self._current_content += chunk
        if not self._pending_flush:
            self._pending_flush = True
            self._flush_timer.start()

    def _flush_markdown(self):
        self._pending_flush = False
        try:
            self.chat_display.setMarkdown(self._current_content)
            scrollbar = self.chat_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception:
            pass

    def flush(self):
        """Fuerza un repintado inmediato del markdown acumulado."""
        if self._flush_timer.isActive():
            self._flush_timer.stop()
        self._flush_markdown()

    def append_user_message(self, message: str):
        self._current_content += f"\n\n**Tú:** {message}\n\n**IA:** "
        self.flush()
        self.set_status("Generando respuesta...")

    def set_error(self, error_msg: str):
        self._current_content += f"\n\n> ❌ **Error:** {error_msg}\n\n"
        self.flush()
        self.set_status("Error", True)

    def _on_send(self):
        text = self.input_field.text().strip()
        if text:
            self.input_field.clear()
            self.append_user_message(text)
            self.send_message.emit(text)

    def reset(self):
        if self._flush_timer.isActive():
            self._flush_timer.stop()
        self._pending_flush = False
        self._current_content = ""
        self.chat_display.clear()
        self.set_status("Esperando datos...", False)
