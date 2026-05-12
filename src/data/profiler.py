import polars as pl
from typing import Dict, Any

def profile_dataset(df: pl.DataFrame) -> Dict[str, Any]:
    """Profiles the dataframe and returns metadata for the Context tab."""
    if df.is_empty():
        return {}
        
    num_rows = df.height
    num_cols = df.width
    memory_mb = df.estimated_size() / (1024 * 1024)
    
    columns_info = []
    
    # We can do some aggregations faster together, but for MVP loop is okay
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
            if series.dtype in pl.NUMERIC_DTYPES:
                info["min"] = series.min()
                info["max"] = series.max()

            elif series.dtype in (pl.Utf8, pl.String, pl.Categorical):
                info["unique"] = series.n_unique()

            elif series.dtype in (pl.Date, pl.Datetime):
                info["min"] = str(series.min())
                info["max"] = str(series.max())
        except Exception:
            pass # ignore if a calculation fails

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
        "columns": columns_info
    }
