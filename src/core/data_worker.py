from PySide6.QtCore import QObject, Signal
from data.reader import read_dataset
from data.profiler import profile_dataset
from data.cleaner import generate_recommendations
import polars as pl
import traceback
import threading

class DataLoaderManager(QObject):
    dataset_loaded = Signal(object)
    progress_updated = Signal(float, str)
    error_occurred = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._thread = None
        self._cancel_flag = False
        
    def load_file(self, file_path: str):
        self._cancel_flag = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.1)
            
        self._cancel_flag = False
        self._thread = threading.Thread(target=self._run_load, args=(file_path,))
        self._thread.daemon = True
        self._thread.start()
        
    def _run_load(self, file_path: str):
        try:
            df = read_dataset(
                file_path,
                progress_callback=self.progress_updated.emit,
                check_cancel=lambda: self._cancel_flag
            )
            if not self._cancel_flag:
                self.dataset_loaded.emit(df)
        except Exception as e:
            self.error_occurred.emit(str(e))
            traceback.print_exc()

class ProfilerManager(QObject):
    profile_ready = Signal(dict, list)
    error_occurred = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._thread = None
        
    def run_profile(self, df: pl.DataFrame):
        self._thread = threading.Thread(target=self._run_profile, args=(df,))
        self._thread.daemon = True
        self._thread.start()
        
    def _run_profile(self, df: pl.DataFrame):
        try:
            profile = profile_dataset(df)
            recs = generate_recommendations(df)
            self.profile_ready.emit(profile, recs)
        except Exception as e:
            self.error_occurred.emit(str(e))
            traceback.print_exc()
