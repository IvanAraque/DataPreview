import polars as pl
from typing import List, Dict, Any

def select_charts(df: pl.DataFrame, max_charts: int = 6) -> List[Dict[str, Any]]:
    """Selects up to `max_charts` interesting columns/pairs to visualize."""
    if df.is_empty():
        return []
        
    charts = []
    date_cols = []
    num_cols = []
    cat_cols = []

    for col in df.columns:
        dtype = df[col].dtype
        if dtype in pl.NUMERIC_DTYPES:
            num_cols.append(col)
        elif dtype in (pl.Date, pl.Datetime):
            date_cols.append(col)
        elif dtype in (pl.Utf8, pl.String, pl.Categorical):
            try:
                unique_count = df[col].n_unique()
                if 1 < unique_count < 50:
                    cat_cols.append(col)
            except Exception:
                pass
                
    # Estrategia: mezcla priorizando lo analítico
    # 1. Líneas date vs cada numérica (evolución temporal)
    if date_cols:
        for num in num_cols:
            if len(charts) >= max_charts: break
            charts.append({"type": "line", "x": date_cols[0], "y": num, "y_": num})

    # 2. Scatter entre cada par de numéricas (combos importantes)
    for i in range(len(num_cols)):
        for j in range(i + 1, len(num_cols)):
            if len(charts) >= max_charts: break
            charts.append({"type": "scatter", "x": num_cols[i], "y": num_cols[j]})
        if len(charts) >= max_charts: break

    # 3. Frecuencia de cada categórica
    for cat in cat_cols:
        if len(charts) >= max_charts: break
        charts.append({"type": "bar", "x": cat, "y": "count"})

    # 4. Distribución de cada numérica
    for num in num_cols:
        if len(charts) >= max_charts: break
        charts.append({"type": "hist", "x": num, "y": "frequency"})

    # Limpieza: quitar campo auxiliar y deduplicar
    seen = set()
    out = []
    for c in charts:
        key = (c.get("type"), c.get("x"), c.get("y"))
        if key in seen:
            continue
        seen.add(key)
        c.pop("y_", None)
        out.append(c)

    return out[:max_charts]
