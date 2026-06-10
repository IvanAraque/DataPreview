import polars as pl
from typing import List, Dict, Any

def generate_recommendations(df: pl.DataFrame) -> List[Dict[str, str]]:
    """Genera una lista de recomendaciones de limpieza basadas en heurísticas."""
    recs = []
    
    if df.is_empty():
        return recs
        
    num_rows = df.height
    
    for col in df.columns:
        series = df[col]
        dtype = series.dtype
        
        # 1. Comprobación de nulos
        null_count = series.null_count()
        if null_count > 0:
            pct = (null_count / num_rows) * 100
            if pct > 50:
                recs.append({
                    "columna": col,
                    "problema": f"{pct:.1f}% de valores nulos",
                    "severidad": "Alta",
                    "sugerencia": "Considerar eliminar la columna"
                })
            else:
                recs.append({
                    "columna": col,
                    "problema": f"{pct:.1f}% de valores nulos",
                    "severidad": "Media",
                    "sugerencia": "Imputar valores o eliminar filas"
                })
                
        # 2. Outliers (IQR) en numéricas
        if dtype in pl.NUMERIC_DTYPES:
            try:
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                if q1 is not None and q3 is not None:
                    iqr = q3 - q1
                    lower_bound = q1 - 1.5 * iqr
                    upper_bound = q3 + 1.5 * iqr
                    
                    outliers = series.filter((series < lower_bound) | (series > upper_bound)).len()
                    if outliers > 0:
                        pct_out = (outliers / num_rows) * 100
                        recs.append({
                            "columna": col,
                            "problema": f"{outliers} outliers detectados ({pct_out:.1f}%)",
                            "severidad": "Alta" if pct_out > 5 else "Media",
                            "sugerencia": "Revisar distribución y acotar valores extremos"
                        })
            except Exception:
                pass
                
        # 3. Comprobaciones de texto categórico
        if dtype in (pl.Utf8, pl.String):
            try:
                unique_pct = series.n_unique() / num_rows
                
                # Comprobar emails y URLs sobre una muestra para no agotar memoria en datasets enormes
                sample = series.drop_nulls().head(20000)
                sample_rows = sample.len()
                
                if sample_rows > 0:
                    if "email" in col.lower() or "correo" in col.lower() or sample.str.contains(r"^[\w\.-]+@[\w\.-]+\.\w+$").sum() > sample_rows * 0.1:
                        recs.append({
                            "columna": col,
                            "problema": "Contiene direcciones de correo (PII)",
                            "severidad": "Alta",
                            "sugerencia": "Considerar enmascarar u omitir esta columna por privacidad"
                        })
                    elif sample.str.contains(r"^https?://").sum() > sample_rows * 0.1:
                        recs.append({
                            "columna": col,
                            "problema": "Contiene URLs",
                            "severidad": "Baja",
                            "sugerencia": "Útil como metadato, pero agrupar por dominio si se usa en BI"
                        })
                    elif 0.95 < unique_pct < 1.0 and "id" not in col.lower():
                        recs.append({
                            "columna": col,
                            "problema": "Alta cardinalidad en texto",
                            "severidad": "Baja",
                            "sugerencia": "Útil para NLP, poco útil para agrupaciones en BI"
                        })
            except Exception:
                pass
                
    return recs
