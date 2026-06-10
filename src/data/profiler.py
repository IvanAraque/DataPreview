import polars as pl
from typing import Dict, Any, List

def profile_dataset(df: pl.DataFrame) -> Dict[str, Any]:
    """Perfila el dataframe y devuelve metadatos para la pestaña Contexto."""
    if df.is_empty():
        return {}

    num_rows = df.height
    num_cols = df.width
    memory_mb = df.estimated_size() / (1024 * 1024)

    columns_info = []

    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        null_count = series.null_count()
        null_percent = (null_count / num_rows) * 100 if num_rows > 0 else 0

        info = {
            "name": col,
            "type": dtype,
            "nulls": f"{null_count} ({null_percent:.1f}%)"
        }

        try:
            # n_unique para TODAS las columnas: ayuda a la IA a detectar
            # identificadores (unicos ~ filas) y categoricas de baja cardinalidad.
            info["unique"] = series.n_unique()
        except Exception:
            pass

        try:
            if series.dtype in pl.NUMERIC_DTYPES:
                info["min"] = series.min()
                info["max"] = series.max()
                mean = series.mean()
                if mean is not None:
                    info["mean"] = round(float(mean), 3)

            elif series.dtype in (pl.Date, pl.Datetime):
                info["min"] = str(series.min())
                info["max"] = str(series.max())
        except Exception:
            pass # ignorar si falla algún cálculo

        # Capturar hasta 5 valores no-nulos para que la IA pueda deducir formatos
        try:
            sample_values = (
                series.drop_nulls().head(5).to_list()
            )
            info["samples"] = [str(v)[:50] for v in sample_values]
        except Exception:
            info["samples"] = []

        columns_info.append(info)

    return {
        "rows": num_rows,
        "cols": num_cols,
        "memory_mb": round(memory_mb, 2),
        "columns": columns_info,
        # Correlaciones reales entre numéricas: la IA las usa para recomendar
        # gráficos con relaciones que EXISTEN en los datos (y detectar
        # columnas redundantes tipo parte/total).
        "correlations": numeric_correlations(df),
    }


def numeric_correlations(df: pl.DataFrame, max_cols: int = 15,
                         max_pairs: int = 12, sample_rows: int = 50000) -> List[Dict[str, Any]]:
    """
    Calcula correlaciones de Pearson entre pares de columnas numéricas y
    devuelve las `max_pairs` más fuertes (por |r|), ordenadas de mayor a menor.
    Se muestrea el dataframe para que sea barato incluso con datasets grandes.
    """
    try:
        num_cols = [c for c in df.columns if df[c].dtype in pl.NUMERIC_DTYPES]
        # Descartar columnas constantes (correlación indefinida)
        num_cols = [c for c in num_cols if df[c].n_unique() > 1][:max_cols]
        if len(num_cols) < 2:
            return []

        d = df.select(num_cols)
        if d.height > sample_rows:
            d = d.sample(sample_rows, seed=0)

        pairs = []
        for i, a in enumerate(num_cols):
            for b in num_cols[i + 1:]:
                try:
                    dd = d.select([a, b]).drop_nulls()
                    if dd.height < 3:
                        continue
                    r = dd.select(pl.corr(a, b)).item()
                    if r is None or r != r:  # None o NaN
                        continue
                    pairs.append({"x": a, "y": b, "r": round(float(r), 3)})
                except Exception:
                    continue

        pairs.sort(key=lambda p: -abs(p["r"]))
        return pairs[:max_pairs]
    except Exception:
        return []


def compute_chart_stats(df: pl.DataFrame, spec: dict) -> Dict[str, Any]:
    """
    Calcula estadísticas REALES sobre los datos de un gráfico concreto para
    alimentar el prompt de explain_chart. Así las observaciones de la IA se
    basan en cifras de verdad y no en suposiciones a partir de min/max.
    Devuelve un dict (posiblemente vacío) con claves legibles en español.
    """
    type_label_map = {
        "Dispersión (Scatter)": "scatter",
        "Línea": "line",
        "Barras": "bar",
        "Histograma": "hist",
        "Cajas (Boxplot)": "box",
        "Correlación (Heatmap)": "heatmap",
    }
    out: Dict[str, Any] = {}
    try:
        ctype = type_label_map.get(spec.get("type"), str(spec.get("type", "")).lower())
        x = spec.get("x")
        y = spec.get("y")
        if y in ("count", "frequency"):
            y = None
        if x not in df.columns:
            return out
        if y is not None and y not in df.columns:
            y = None

        # Muestrear para abaratar en datasets grandes
        d = df
        if d.height > 100000:
            d = d.sample(100000, seed=0)

        if ctype == "scatter" and y:
            dd = d.select([x, y]).drop_nulls()
            out["n_puntos"] = dd.height
            if dd.height >= 3:
                r = dd.select(pl.corr(x, y)).item()
                if r is not None and r == r:
                    out["correlacion_pearson"] = round(float(r), 3)
            for col, label in ((x, "x"), (y, "y")):
                s = dd[col]
                out[f"media_{label} ({col})"] = _safe_round(s.mean())
                out[f"rango_{label} ({col})"] = f"{_safe_round(s.min())} a {_safe_round(s.max())}"

        elif ctype == "line" and y:
            dd = d.select([x, y]).drop_nulls().sort(x)
            if dd.height >= 2:
                out["n_puntos"] = dd.height
                y0, y1 = dd[y][0], dd[y][-1]
                out[f"primer_valor de {y} (en {x}={dd[x][0]})"] = _safe_round(y0)
                out[f"ultimo_valor de {y} (en {x}={dd[x][-1]})"] = _safe_round(y1)
                out[f"minimo de {y}"] = _safe_round(dd[y].min())
                out[f"maximo de {y}"] = _safe_round(dd[y].max())
                try:
                    if y0 not in (None, 0):
                        out["cambio_total_pct"] = round((float(y1) - float(y0)) / abs(float(y0)) * 100, 1)
                except Exception:
                    pass

        elif ctype in ("hist", "box"):
            s = d[x].drop_nulls()
            if s.len() >= 3 and s.dtype in pl.NUMERIC_DTYPES:
                out["n_valores"] = s.len()
                out["media"] = _safe_round(s.mean())
                out["mediana"] = _safe_round(s.median())
                out["desviacion_tipica"] = _safe_round(s.std())
                q1 = s.quantile(0.25)
                q3 = s.quantile(0.75)
                out["p25"] = _safe_round(q1)
                out["p75"] = _safe_round(q3)
                try:
                    if q1 is not None and q3 is not None:
                        iqr = float(q3) - float(q1)
                        lo, hi = float(q1) - 1.5 * iqr, float(q3) + 1.5 * iqr
                        n_out = s.filter((s < lo) | (s > hi)).len()
                        out["outliers_segun_IQR"] = n_out
                except Exception:
                    pass

        elif ctype == "bar":
            s = d[x].drop_nulls()
            if s.len() > 0:
                vc = (
                    d.select(x).drop_nulls()
                    .group_by(x).len()
                    .sort("len", descending=True)
                    .head(8)
                )
                total = s.len()
                tops = [
                    f"{row[0]}: {row[1]} ({row[1] / total * 100:.1f}%)"
                    for row in vc.iter_rows()
                ]
                out["n_categorias"] = s.n_unique()
                out["top_categorias"] = "; ".join(tops)
    except Exception:
        pass
    return out


def _safe_round(v, nd: int = 3):
    try:
        return round(float(v), nd)
    except Exception:
        return v
