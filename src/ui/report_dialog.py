"""
Diálogo de generación de informe / memoria de análisis.

Captura los gráficos del PreviewTab a PNG (base64), pide a la IA los textos
de las secciones y construye un HTML autocontenido (CSS inline, imágenes
embebidas) que el usuario puede descargar como un único archivo.
"""

from __future__ import annotations

import base64
import datetime
import html as html_lib
import io
import os
import traceback
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, Signal, QByteArray, QBuffer, QIODevice, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QFileDialog, QMessageBox, QSizePolicy,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

import qtawesome as qta


# ---------------------------------------------------------------------------
# Helpers de captura → base64 PNG
# ---------------------------------------------------------------------------

def _widget_to_base64_png(widget, max_width: int = 1200) -> Optional[str]:
    """Renderiza un QWidget a un PNG en base64. None si no se pudo capturar."""
    if widget is None:
        return None
    try:
        pixmap: QPixmap = widget.grab()
        if pixmap.isNull() or pixmap.width() == 0:
            return None
        # Reescalar si es muy ancho (para no inflar el HTML)
        if pixmap.width() > max_width:
            pixmap = pixmap.scaledToWidth(max_width, Qt.SmoothTransformation)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        ok = pixmap.save(buf, "PNG")
        buf.close()
        if not ok:
            return None
        return bytes(ba.toBase64()).decode("ascii")
    except Exception:
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# CSS del informe (inline en el HTML final, autocontenido)
# ---------------------------------------------------------------------------

_REPORT_CSS = """
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
    font-family: Verdana, "Segoe UI", Arial, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    color: #1F2937;
    background: #FFFFFF;
    max-width: 920px;
    margin: 0 auto;
    padding: 40px 36px 80px 36px;
}
header.cover {
    border-bottom: 2px solid #4F46E5;
    padding-bottom: 20px;
    margin-bottom: 28px;
}
header.cover h1 {
    margin: 0 0 6px 0;
    font-size: 28px;
    color: #1F2937;
    font-weight: 700;
}
header.cover .meta {
    color: #6B7280;
    font-size: 13px;
    margin-top: 2px;
}
nav.toc {
    background: #F3F4F6;
    border-left: 4px solid #4F46E5;
    padding: 14px 22px;
    margin: 24px 0 36px 0;
}
nav.toc h2 {
    margin: 0 0 6px 0;
    font-size: 15px;
    color: #4F46E5;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}
nav.toc ol { margin: 6px 0 0 20px; padding: 0; }
nav.toc li { margin: 2px 0; }
nav.toc a { color: #1F2937; text-decoration: none; }
nav.toc a:hover { color: #4F46E5; text-decoration: underline; }
section { margin-top: 30px; }
section h2 {
    color: #1F2937;
    border-bottom: 1px solid #E5E7EB;
    padding-bottom: 6px;
    margin-top: 34px;
    font-size: 22px;
}
section h3 {
    color: #374151;
    margin-top: 22px;
    font-size: 17px;
}
section p { margin: 10px 0; text-align: justify; }
table.stats {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 13px;
}
table.stats th, table.stats td {
    text-align: left;
    padding: 7px 10px;
    border-bottom: 1px solid #E5E7EB;
}
table.stats th {
    background: #F3F4F6;
    color: #374151;
    font-weight: 600;
}
table.stats tr:nth-child(even) td { background: #FAFAFA; }
.cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 18px 0 24px 0;
}
.card {
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 12px 14px;
    background: #FAFAFA;
}
.card .label {
    font-size: 11px;
    color: #6B7280;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}
.card .value {
    font-size: 22px;
    font-weight: 600;
    margin-top: 4px;
    color: #1F2937;
}
.chart-block {
    margin: 26px 0 32px 0;
}
.chart-block img {
    max-width: 100%;
    display: block;
    margin: 8px auto 12px auto;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
}
.chart-block .desc {
    font-style: italic;
    color: #4338CA;
    margin: 2px 0 8px 0;
}
.chart-block .obs {
    margin: 6px 0;
}
.callout {
    background: #EEF2FF;
    border-left: 3px solid #4F46E5;
    padding: 12px 16px;
    margin: 18px 0;
    border-radius: 4px;
}
.callout strong { color: #4338CA; }
footer.report-foot {
    margin-top: 50px;
    padding-top: 14px;
    border-top: 1px solid #E5E7EB;
    color: #9CA3AF;
    font-size: 12px;
    text-align: center;
}
"""


# ---------------------------------------------------------------------------
# Constructor del HTML
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    return html_lib.escape(str(text or ""))


def _paragraphs(text: str) -> str:
    """Convierte texto plano con saltos de párrafo en <p>...</p>."""
    text = (text or "").strip()
    if not text:
        return ""
    out = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if chunk:
            # Permitir saltos de línea simples dentro de un párrafo como <br>
            out.append("<p>" + _esc(chunk).replace("\n", "<br>") + "</p>")
    return "\n".join(out)


def build_report_html(
    title: str,
    dataset_name: str,
    profile: dict,
    chart_blocks: List[Dict],
    cleaning_recs: List[Dict],
    ai_sections: Optional[Dict[str, str]] = None,
) -> str:
    """
    Construye el HTML completo del informe.
    - `chart_blocks`: lista de dicts {"title", "image_b64", "description", "observations"}.
    - `ai_sections`: dict con campos abstract / introduction / intro_eda /
      cleaning_section / conclusions. Si None o vacío, se usa fallback factual.
    """
    ai = ai_sections or {}
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    rows = profile.get("rows", 0)
    cols = profile.get("cols", 0)
    memory = profile.get("memory_mb", 0)
    columns_info = profile.get("columns", []) or []

    type_count = len({(c.get("type") or "").split("(")[0].strip() for c in columns_info})

    # Número formateado con "." de separador de miles (estilo español)
    rows_str = f"{rows:,}".replace(",", ".")

    # ----- Secciones de prosa -----
    abstract = ai.get("abstract") or (
        f"En las páginas siguientes se recoge un análisis exploratorio del "
        f"conjunto de datos «{dataset_name or 'dataset'}», con {rows_str} filas y "
        f"{cols} columnas. El objetivo es entender la estructura de los datos, "
        f"identificar problemas de calidad y producir las visualizaciones más "
        f"informativas para tomar decisiones sobre los datos."
    )

    introduction = ai.get("introduction") or (
        f"Trabajamos sobre un dataset de {rows_str} filas distribuidas en {cols} "
        f"columnas, que ocupa aproximadamente {memory} MB en memoria. El "
        f"propósito del análisis es doble: comprender qué hay dentro del "
        f"conjunto y producir un primer mapa visual de las variables más "
        f"relevantes. A lo largo del informe revisamos primero la composición "
        f"del dataset, después un bloque de análisis exploratorio con las "
        f"visualizaciones recomendadas, y finalmente las observaciones sobre "
        f"calidad de los datos y las conclusiones de negocio."
    )

    intro_eda = ai.get("intro_eda") or (
        "A continuación se muestran las visualizaciones más relevantes del "
        "dataset. Cada una se acompaña de una breve descripción del gráfico "
        "y de las observaciones que se extraen de los datos representados."
    )

    cleaning_text = ai.get("cleaning_section") or (
        "Las heurísticas automáticas y la revisión manual de las muestras "
        "detectan los siguientes puntos a tener en cuenta antes de cualquier "
        "análisis posterior."
    )

    conclusions = ai.get("conclusions") or (
        "El recorrido por el dataset deja una imagen clara de su composición "
        "y de sus puntos débiles. Las visualizaciones del bloque exploratorio "
        "son un buen punto de partida para preguntas más específicas, y los "
        "problemas de calidad detectados deberían resolverse antes de "
        "abordar un modelado predictivo serio sobre estos datos."
    )

    # ----- Cards de resumen -----
    cards_html = (
        f'<div class="cards">'
        f'<div class="card"><div class="label">Filas</div><div class="value">{rows:,}</div></div>'
        f'<div class="card"><div class="label">Columnas</div><div class="value">{cols}</div></div>'
        f'<div class="card"><div class="label">Memoria</div><div class="value">{memory} MB</div></div>'
        f'<div class="card"><div class="label">Tipos</div><div class="value">{type_count}</div></div>'
        f"</div>"
    ).replace(",", ".")

    # ----- Tabla de columnas -----
    cols_rows_html = []
    for c in columns_info:
        cols_rows_html.append(
            "<tr>"
            f"<td>{_esc(c.get('name'))}</td>"
            f"<td>{_esc(c.get('type'))}</td>"
            f"<td>{_esc(c.get('nulls'))}</td>"
            f"<td>{_esc(c.get('unique', ''))}</td>"
            f"<td>{_esc(c.get('min', ''))}</td>"
            f"<td>{_esc(c.get('max', ''))}</td>"
            "</tr>"
        )
    cols_table_html = (
        '<table class="stats">'
        "<thead><tr>"
        "<th>Columna</th><th>Tipo</th><th>Nulos</th>"
        "<th>Únicos</th><th>Mínimo</th><th>Máximo</th>"
        "</tr></thead>"
        "<tbody>" + "".join(cols_rows_html) + "</tbody>"
        "</table>"
    )

    # ----- Gráficos -----
    charts_html_parts = []
    for i, cb in enumerate(chart_blocks, start=1):
        title_c = cb.get("title") or f"Gráfico {i}"
        b64 = cb.get("image_b64")
        desc = cb.get("description") or ""
        obs = cb.get("observations") or ""
        img_html = (
            f'<img src="data:image/png;base64,{b64}" alt="{_esc(title_c)}" />'
            if b64 else
            '<p><em>(No se pudo capturar la imagen de este gráfico.)</em></p>'
        )
        block = (
            '<div class="chart-block">'
            f'<h3>4.{i}. {_esc(title_c)}</h3>'
            f"{img_html}"
            + (f'<p class="desc">{_esc(desc)}</p>' if desc else "")
            + (f'<p class="obs">{_esc(obs)}</p>' if obs else "")
            + "</div>"
        )
        charts_html_parts.append(block)
    charts_html = "\n".join(charts_html_parts) if charts_html_parts else (
        "<p><em>No hay gráficos generados para incluir en el informe.</em></p>"
    )

    # ----- Limpieza -----
    cleaning_rows = []
    for r in (cleaning_recs or [])[:50]:
        cleaning_rows.append(
            "<tr>"
            f"<td>{_esc(r.get('columna'))}</td>"
            f"<td>{_esc(r.get('severidad'))}</td>"
            f"<td>{_esc(r.get('problema'))}</td>"
            f"<td>{_esc(r.get('sugerencia'))}</td>"
            "</tr>"
        )
    if cleaning_rows:
        cleaning_table = (
            '<table class="stats">'
            "<thead><tr><th>Columna</th><th>Severidad</th><th>Problema</th><th>Sugerencia</th></tr></thead>"
            "<tbody>" + "".join(cleaning_rows) + "</tbody>"
            "</table>"
        )
    else:
        cleaning_table = '<p><em>No se han detectado problemas de calidad reseñables.</em></p>'

    # ----- HTML final -----
    safe_title = _esc(title or "Informe de análisis")
    safe_ds = _esc(dataset_name or "dataset")

    return (
        '<!DOCTYPE html>\n'
        '<html lang="es">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        f'<title>{safe_title}</title>\n'
        f'<style>{_REPORT_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        '<header class="cover">\n'
        f'  <h1>{safe_title}</h1>\n'
        f'  <div class="meta">Dataset analizado: <strong>{safe_ds}</strong></div>\n'
        f'  <div class="meta">Generado el {now}</div>\n'
        '</header>\n'
        '<nav class="toc">\n'
        '  <h2>Índice</h2>\n'
        '  <ol>\n'
        '    <li><a href="#resumen">Resumen</a></li>\n'
        '    <li><a href="#introduccion">Introducción</a></li>\n'
        '    <li><a href="#descripcion">Descripción del dataset</a></li>\n'
        '    <li><a href="#exploratorio">Análisis exploratorio</a></li>\n'
        '    <li><a href="#calidad">Calidad de los datos</a></li>\n'
        '    <li><a href="#conclusiones">Conclusiones</a></li>\n'
        '  </ol>\n'
        '</nav>\n'
        '<section id="resumen">\n'
        '  <h2>1. Resumen</h2>\n'
        f'  {_paragraphs(abstract)}\n'
        '</section>\n'
        '<section id="introduccion">\n'
        '  <h2>2. Introducción</h2>\n'
        f'  {_paragraphs(introduction)}\n'
        '</section>\n'
        '<section id="descripcion">\n'
        '  <h2>3. Descripción del dataset</h2>\n'
        f'  <p>El conjunto se compone de <strong>{rows_str}</strong> filas y <strong>{cols}</strong> columnas, ocupando aproximadamente <strong>{memory} MB</strong> de memoria.</p>\n'
        f'  {cards_html}\n'
        '  <h3>3.1. Estructura por columnas</h3>\n'
        f'  {cols_table_html}\n'
        '</section>\n'
        '<section id="exploratorio">\n'
        '  <h2>4. Análisis exploratorio</h2>\n'
        f'  {_paragraphs(intro_eda)}\n'
        f'  {charts_html}\n'
        '</section>\n'
        '<section id="calidad">\n'
        '  <h2>5. Calidad de los datos</h2>\n'
        f'  {_paragraphs(cleaning_text)}\n'
        f'  {cleaning_table}\n'
        '</section>\n'
        '<section id="conclusiones">\n'
        '  <h2>6. Conclusiones</h2>\n'
        f'  {_paragraphs(conclusions)}\n'
        '</section>\n'
        '<footer class="report-foot">\n'
        '  Informe generado por DataPreview\n'
        '</footer>\n'
        '</body>\n'
        '</html>\n'
    )


# ---------------------------------------------------------------------------
# Diálogo del informe
# ---------------------------------------------------------------------------

class ReportDialog(QDialog):
    """
    Ventana propia (no modal) que muestra el informe en un WebEngineView y
    ofrece un botón para descargarlo como .html autocontenido.
    """

    # Señal que el MainWindow conecta para lanzar la petición a la IA
    request_ai_sections = Signal(dict)  # payload con profile, samples, ...

    def __init__(self, *, dataset_name: str, profile: dict, samples: dict,
                 chart_blocks: List[Dict], cleaning_recs: List[Dict],
                 ai_available: bool, context_text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informe de análisis")
        self.resize(1100, 800)
        self.setModal(False)

        self._dataset_name = dataset_name or "dataset"
        self._profile = profile or {}
        self._samples = samples or {}
        self._chart_blocks = list(chart_blocks or [])
        self._cleaning_recs = list(cleaning_recs or [])
        self._ai_available = bool(ai_available)
        self._context_text = context_text or ""
        self._ai_sections: Optional[Dict[str, str]] = None
        self._last_html: str = ""
        self._title: str = f"Informe de análisis: {self._dataset_name}"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Barra superior: estado + botón descargar
        topbar = QHBoxLayout()
        topbar.setContentsMargins(14, 10, 14, 10)
        self.status_lbl = QLabel("Preparando informe…")
        self.status_lbl.setStyleSheet("color: #6B7280;")
        topbar.addWidget(self.status_lbl)
        topbar.addStretch(1)

        self.download_btn = QPushButton(
            qta.icon("fa5s.download", color="white"), " Descargar HTML"
        )
        self.download_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #4F46E5; color: white;"
            "  font-size: 13px; font-weight: 600;"
            "  padding: 8px 16px; border-radius: 6px;"
            "}"
            "QPushButton:hover { background-color: #4338CA; }"
            "QPushButton:disabled { background-color: rgba(127,127,127,0.25); color: rgba(255,255,255,0.6); }"
        )
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._on_download_clicked)
        topbar.addWidget(self.download_btn)

        self.close_btn = QPushButton("Cerrar")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        topbar.addWidget(self.close_btn)

        outer.addLayout(topbar)

        # Barra de progreso indeterminada
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminada (oscila)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        outer.addWidget(self.progress)

        # WebView con el informe
        if WEBENGINE_AVAILABLE:
            self.webview = QWebEngineView()
            outer.addWidget(self.webview, 1)
        else:
            self.webview = None
            outer.addWidget(QLabel("QWebEngineView no está disponible — se mostrará texto plano."), 1)

        # Construye HTML inicial con prosa fallback y muestralo mientras
        # la IA piensa. Si no hay IA, ya es la versión final.
        self._render_html(use_fallback=True)

        if self._ai_available:
            self.status_lbl.setText("Pidiendo prosa a la IA… (puedes esperar; al final igualmente se podrá descargar)")
            # Pequeño delay para que el WebView ya haya pintado algo antes de
            # esperar a la IA (mejor UX, ves el informe formándose).
            QTimer.singleShot(50, self._emit_ai_request)
            # Watchdog: si en 6 min no respondió la IA, habilitamos descarga
            # con la prosa básica (si la IA llega más tarde, refrescará el HTML).
            QTimer.singleShot(360000, self._on_ai_watchdog)
        else:
            self._finalize(ai_failed=False)

    # ----- API -----------------------------------------------------------

    def apply_ai_sections(self, sections: Dict[str, str]):
        """MainWindow nos pasa por aquí la respuesta de la IA."""
        if not isinstance(sections, dict):
            self._finalize(ai_failed=True)
            return
        self._ai_sections = sections
        title_suggestion = (sections.get("title_suggestion") or "").strip()
        if title_suggestion:
            self._title = title_suggestion
            self.setWindowTitle(self._title)
        self._render_html(use_fallback=False)
        self._finalize(ai_failed=False)

    def apply_ai_error(self, _error_msg: str):
        # El HTML con fallback ya está mostrado; solo cerramos el loading.
        self._finalize(ai_failed=True)

    # ----- Internos ------------------------------------------------------

    def _emit_ai_request(self):
        payload = {
            "dataset_name": self._dataset_name,
            "profile": self._profile,
            "samples": self._samples,
            "context_text": self._context_text,
            "chart_summaries": [
                {
                    "type": cb.get("spec", {}).get("type"),
                    "x": cb.get("spec", {}).get("x"),
                    "y": cb.get("spec", {}).get("y"),
                    "description": cb.get("description"),
                    "observations": cb.get("observations"),
                }
                for cb in self._chart_blocks
            ],
            "cleaning_summary": self._cleaning_recs,
        }
        self.request_ai_sections.emit(payload)

    def _render_html(self, use_fallback: bool):
        html = build_report_html(
            title=self._title,
            dataset_name=self._dataset_name,
            profile=self._profile,
            chart_blocks=self._chart_blocks,
            cleaning_recs=self._cleaning_recs,
            ai_sections=None if use_fallback else self._ai_sections,
        )
        self._last_html = html
        if self.webview is not None:
            try:
                self.webview.setHtml(html)
            except Exception:
                traceback.print_exc()

    def _on_ai_watchdog(self):
        # Si todavía no llegó la IA, habilitamos descarga con la versión básica.
        if self._ai_sections is None and not self.download_btn.isEnabled():
            self.status_lbl.setText(
                "La IA está tardando. Puedes descargar la prosa básica; "
                "si llega, se actualizará."
            )
            self.download_btn.setEnabled(True)

    def _finalize(self, ai_failed: bool):
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        if ai_failed:
            self.status_lbl.setText("Informe listo (prosa básica; la IA no respondió).")
        elif self._ai_sections:
            self.status_lbl.setText("Informe listo.")
        else:
            self.status_lbl.setText("Informe listo (modo sin IA).")
        self.download_btn.setEnabled(True)

    def _on_download_clicked(self):
        default_name = self._safe_filename(self._dataset_name) or "informe"
        default_path = os.path.join(
            os.path.expanduser("~"),
            f"informe_{default_name}.html",
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar informe",
            default_path,
            "HTML (*.html)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._last_html)
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))
            return
        QMessageBox.information(
            self, "Informe guardado",
            f"Se ha guardado en:\n{path}\n\nPuedes abrirlo con doble clic en cualquier navegador.",
        )

    @staticmethod
    def _safe_filename(name: str) -> str:
        if not name:
            return ""
        base = os.path.splitext(os.path.basename(str(name)))[0]
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in base)
        return safe[:60]
