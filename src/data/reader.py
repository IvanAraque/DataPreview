import polars as pl
import os
import time
from typing import Callable, Optional

def _estimate_total_lines(file_path: str) -> int:
    """Estimates the total number of lines in a file by sampling the first 1MB."""
    total_bytes = os.path.getsize(file_path)
    if total_bytes == 0:
        return 1
        
    try:
        with open(file_path, 'rb') as f:
            head = f.read(1024 * 1024) # Read up to 1MB
            lines = head.count(b'\n')
            if lines == 0:
                return 1
            bytes_per_line = len(head) / lines
            return max(1, int(total_bytes / bytes_per_line))
    except Exception:
        return 1

def read_dataset(
    file_path: str, 
    progress_callback: Optional[Callable[[float, str], None]] = None, 
    check_cancel: Optional[Callable[[], bool]] = None
) -> pl.DataFrame:
    """
    Reads a dataset and reports progress.
    progress_callback(percentage: float, time_estimate_str: str)
    """
    ext = os.path.splitext(file_path)[1].lower()
    start_time = time.time()
    
    if ext == ".csv":
        total_estimated_lines = _estimate_total_lines(file_path)
        
        try:
            reader = pl.read_csv_batched(file_path, ignore_errors=True)
            batches = reader.next_batches(50)
        except Exception:
            # Fallback for small or problematic CSVs
            if progress_callback:
                progress_callback(100.0, "0s")
            return pl.read_csv(file_path, ignore_errors=True)
            
        chunks = []
        total_rows_read = 0
        
        while batches:
            if check_cancel and check_cancel():
                return pl.DataFrame()
                
            for batch in batches:
                chunks.append(batch)
                total_rows_read += batch.height
                
            elapsed = time.time() - start_time
            if total_rows_read > 0:
                percentage = min(100.0, (total_rows_read / total_estimated_lines) * 100)
                rows_per_sec = total_rows_read / elapsed
                remaining_rows = total_estimated_lines - total_rows_read
                est_seconds_left = remaining_rows / rows_per_sec if rows_per_sec > 0 else 0
                
                time_str = f"{max(0, int(est_seconds_left))}s"
                
                if progress_callback:
                    progress_callback(percentage, time_str)
            
            batches = reader.next_batches(50)
            
        if chunks:
            # Concat all chunks
            df = pl.concat(chunks)
        else:
            df = pl.DataFrame()
            
        if progress_callback:
            progress_callback(100.0, "0s")
            
        return df
        
    elif ext == ".xlsx":
        # Polars can read excel, but it might not support chunking well.
        # We just report 0 then 100.
        if progress_callback:
            progress_callback(50.0, "...")
        df = pl.read_excel(file_path)
        if progress_callback:
            progress_callback(100.0, "0s")
        return df
        
    elif ext == ".parquet":
        df = pl.read_parquet(file_path)
        if progress_callback:
            progress_callback(100.0, "0s")
        return df
        
    elif ext == ".json":
        df = pl.read_json(file_path)
        if progress_callback:
            progress_callback(100.0, "0s")
        return df
        
    else:
        raise ValueError(f"Formato no soportado: {ext}")
