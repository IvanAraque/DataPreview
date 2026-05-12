import pyqtgraph as pg
import polars as pl
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from typing import Dict, Any

def create_chart_widget(df: pl.DataFrame, chart_def: Dict[str, Any]) -> QWidget:
    container = QWidget()
    # Add a nice border and white/dark background matching the theme
    container.setObjectName("chartContainer")
    container.setStyleSheet("""
        QWidget#chartContainer {
            background-color: transparent;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
        }
    """)
    
    layout = QVBoxLayout(container)
    layout.setContentsMargins(15, 15, 15, 15)
    
    ctype = chart_def["type"]
    x_col = chart_def["x"]
    y_col = chart_def.get("y")
    
    # Title Label (cleaner than pg.PlotWidget title)
    title_text = f"{ctype.capitalize()}: {x_col}" + (f" vs {y_col}" if y_col and y_col not in ("count", "frequency") else "")
    title_lbl = QLabel(f"<b>{title_text}</b>")
    title_lbl.setStyleSheet("border: none; font-size: 13px; color: #6B7280;")
    layout.addWidget(title_lbl)
    
    plot_widget = pg.PlotWidget()
    plot_widget.setBackground('transparent')
    
    # Clean up axes
    plot_widget.getAxis('left').setPen(pg.mkPen(color='#D1D5DB', width=1))
    plot_widget.getAxis('bottom').setPen(pg.mkPen(color='#D1D5DB', width=1))
    plot_widget.getAxis('left').setTextPen(pg.mkPen(color='#6B7280'))
    plot_widget.getAxis('bottom').setTextPen(pg.mkPen(color='#6B7280'))
    plot_widget.showGrid(x=False, y=True, alpha=0.2)
    
    # Colors
    accent_color = '#4F46E5'
    
    try:
        # Pre-clean data for NaNs and Infs to prevent PyQtGraph C++ segfaults
        clean_df = df
        for col in [x_col, y_col]:
            if col and col in df.columns and df[col].dtype in pl.NUMERIC_DTYPES:
                clean_df = clean_df.filter(pl.col(col).is_finite())
                
        if ctype == "hist":
            data = clean_df[x_col].drop_nulls().head(100000).to_numpy()
            if len(data) > 0:
                y, x = np.histogram(data, bins=20)
                bg = pg.BarGraphItem(x0=x[:-1], x1=x[1:], height=y, brush=accent_color, pen=None)
                plot_widget.addItem(bg)
                
        elif ctype == "bar":
            counts = clean_df[x_col].value_counts().sort(x_col)
            if counts.height > 8:
                counts = counts.sort("count", descending=True).head(8)
                
            raw_labels = counts[x_col].cast(pl.Utf8).fill_null("N/A").to_list()
            # Truncate long labels so they don't overlap
            x_labels = [s[:10] + ".." if len(s) > 10 else s for s in raw_labels]
            y_vals = counts["count"].to_numpy()
            x_pos = np.arange(len(x_labels))
            
            bg = pg.BarGraphItem(x=x_pos, height=y_vals, width=0.5, brush=accent_color, pen=None)
            plot_widget.addItem(bg)
            
            ax = plot_widget.getAxis('bottom')
            ticks = [list(zip(x_pos, x_labels))]
            ax.setTicks(ticks)
            
        elif ctype == "scatter":
            x_data = clean_df[x_col].drop_nulls().head(5000).to_numpy()
            y_data = clean_df[y_col].drop_nulls().head(5000).to_numpy()
            min_len = min(len(x_data), len(y_data))
            
            scatter = pg.ScatterPlotItem(
                x=x_data[:min_len], y=y_data[:min_len], 
                pen=None, brush=pg.mkBrush(79, 70, 229, 150), size=6
            )
            plot_widget.addItem(scatter)
            
        elif ctype == "line":
            sorted_df = clean_df.select([x_col, y_col]).drop_nulls().sort(x_col).head(2000)
            x_data = np.arange(sorted_df.height)
            y_data = sorted_df[y_col].to_numpy()
            
            plot_widget.plot(x_data, y_data, pen=pg.mkPen(color=accent_color, width=2))
            
    except Exception as e:
        error_label = QLabel(f"Error: {e}")
        error_label.setStyleSheet("color: red; border: none;")
        layout.addWidget(error_label)
        return container
        
    layout.addWidget(plot_widget)
    return container
