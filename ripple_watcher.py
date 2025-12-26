"""
Ripple Language - CSV 文件监听器
监听 CSV 文件变化，自动触发响应式更新
"""

import os
import time
import threading
from typing import Dict, Callable, Optional

from ripple_engine import _load_csv_file

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object


class CSVFileHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """CSV 文件变化处理器"""

    def __init__(self, watcher: 'CSVWatcher'):
        if WATCHDOG_AVAILABLE:
            super().__init__()
        self.watcher = watcher
        self._last_modified: Dict[str, float] = {}

    def on_modified(self, event):
        if event.is_directory:
            return

        file_path = os.path.abspath(event.src_path)

        if file_path not in self.watcher.watched_files:
            return

        # 防抖动
        now = time.time()
        last = self._last_modified.get(file_path, 0)
        if now - last < 0.5:
            return
        self._last_modified[file_path] = now

        self.watcher._on_file_changed(file_path)


class CSVWatcher:
    """CSV 文件监听器"""

    def __init__(self):
        self.observer = None
        self.watched_files: Dict[str, Dict] = {}
        self.handler = CSVFileHandler(self) if WATCHDOG_AVAILABLE else None
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def watch(self, path: str, source_name: str, callback: Callable, skip_header: bool = False):
        """注册文件监听"""
        abs_path = os.path.abspath(path)
        try:
            mtime = os.path.getmtime(abs_path)
        except OSError:
            mtime = 0

        self.watched_files[abs_path] = {
            'source_name': source_name,
            'skip_header': skip_header,
            'callback': callback,
            'path': path,
            'mtime': mtime
        }

        if WATCHDOG_AVAILABLE and self._running and self.observer:
            dir_path = os.path.dirname(abs_path)
            self.observer.schedule(self.handler, dir_path, recursive=False)

    def _on_file_changed(self, file_path: str):
        """文件变化回调"""
        if file_path not in self.watched_files:
            return

        info = self.watched_files[file_path]
        source_name = info['source_name']
        skip_header = info['skip_header']
        callback = info['callback']

        try:
            new_data = _load_csv_file(file_path, skip_header)
            callback(source_name, new_data)
        except Exception:
            pass  # 静默处理错误

    def _poll_loop(self):
        """轮询模式主循环"""
        while not self._stop_event.is_set():
            for file_path, info in list(self.watched_files.items()):
                try:
                    current_mtime = os.path.getmtime(file_path)
                    if current_mtime > info['mtime']:
                        info['mtime'] = current_mtime
                        self._on_file_changed(file_path)
                except OSError:
                    pass
            self._stop_event.wait(1.0)

    def start(self):
        """启动文件监听"""
        if self._running or not self.watched_files:
            return

        self._stop_event.clear()

        if WATCHDOG_AVAILABLE:
            self.observer = Observer()
            watched_dirs = set()
            for path in self.watched_files.keys():
                dir_path = os.path.dirname(path)
                if dir_path not in watched_dirs:
                    watched_dirs.add(dir_path)
                    self.observer.schedule(self.handler, dir_path, recursive=False)
            self.observer.start()
        else:
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()

        self._running = True

    def stop(self):
        """停止文件监听"""
        if not self._running:
            return

        self._stop_event.set()

        if WATCHDOG_AVAILABLE and self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        elif self._poll_thread:
            self._poll_thread.join(timeout=2.0)
            self._poll_thread = None

        self._running = False

    def is_running(self) -> bool:
        return self._running
