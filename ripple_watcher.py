"""
Ripple Language - CSV 文件监听器
监听 CSV 文件变化，自动触发响应式更新
支持两种模式：watchdog（如果安装）或轮询模式（备选）
"""

import os
import time
import threading
from typing import Dict, Callable, Optional

from ripple_engine import _load_csv_file

# 尝试导入 watchdog，如果失败则使用轮询模式
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object


class CSVFileHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """CSV 文件变化处理器 (watchdog 模式)"""

    def __init__(self, watcher: 'CSVWatcher'):
        if WATCHDOG_AVAILABLE:
            super().__init__()
        self.watcher = watcher
        self._last_modified: Dict[str, float] = {}  # 防抖动

    def on_modified(self, event):
        if event.is_directory:
            return

        file_path = os.path.abspath(event.src_path)

        # 检查是否是我们监听的文件
        if file_path not in self.watcher.watched_files:
            return

        # 防抖动：忽略 500ms 内的重复事件
        now = time.time()
        last = self._last_modified.get(file_path, 0)
        if now - last < 0.5:
            return
        self._last_modified[file_path] = now

        # 触发回调
        self.watcher._on_file_changed(file_path)


class CSVWatcher:
    """CSV 文件监听器（支持 watchdog 或轮询模式）"""

    def __init__(self):
        self.observer = None
        self.watched_files: Dict[str, Dict] = {}  # path -> {source_name, skip_header, callback, mtime}
        self.handler = CSVFileHandler(self) if WATCHDOG_AVAILABLE else None
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def watch(self, path: str, source_name: str, callback: Callable,
              skip_header: bool = False):
        """
        注册文件监听

        Args:
            path: CSV 文件路径
            source_name: 对应的源节点名称
            callback: 文件变化时的回调函数，接收 (source_name, new_data) 参数
            skip_header: 是否跳过表头
        """
        abs_path = os.path.abspath(path)
        # 记录当前文件的修改时间
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

        # 如果 watchdog observer 已经在运行，添加新的监听目录
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
        display_path = info['path']

        try:
            # 重新加载 CSV 文件
            new_data = _load_csv_file(file_path, skip_header)

            print(f"\n[文件监听] 检测到 '{display_path}' 变化，重新加载...")
            print(f"  加载了 {len(new_data)} 行数据")

            # 调用回调函数更新数据
            callback(source_name, new_data)

        except Exception as e:
            print(f"\n[文件监听] 加载 '{display_path}' 失败: {e}")

    def _poll_loop(self):
        """轮询模式的主循环"""
        while not self._stop_event.is_set():
            for file_path, info in list(self.watched_files.items()):
                try:
                    current_mtime = os.path.getmtime(file_path)
                    if current_mtime > info['mtime']:
                        # 文件已修改
                        info['mtime'] = current_mtime
                        self._on_file_changed(file_path)
                except OSError:
                    pass  # 文件可能暂时不可访问

            # 每秒检查一次
            self._stop_event.wait(1.0)

    def start(self):
        """启动文件监听"""
        if self._running:
            return

        if not self.watched_files:
            return

        self._stop_event.clear()

        if WATCHDOG_AVAILABLE:
            # 使用 watchdog 模式
            self.observer = Observer()

            # 收集所有需要监听的目录
            watched_dirs = set()
            for path in self.watched_files.keys():
                dir_path = os.path.dirname(path)
                if dir_path not in watched_dirs:
                    watched_dirs.add(dir_path)
                    self.observer.schedule(self.handler, dir_path, recursive=False)

            self.observer.start()
            self._running = True
            print(f"[文件监听] 已启动 (watchdog 模式)，监听 {len(self.watched_files)} 个文件")
        else:
            # 使用轮询模式
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()
            self._running = True
            print(f"[文件监听] 已启动 (轮询模式)，监听 {len(self.watched_files)} 个文件")
            print("  提示: 安装 watchdog 可获得更好的性能 (pip install watchdog)")

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
        print("[文件监听] 已停止")

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running


# ==================== 集成到 Runner ====================

class WatchableRunner:
    """支持文件监听的 Ripple 运行器"""

    def __init__(self, engine, csv_sources: Dict[str, Dict]):
        """
        Args:
            engine: RippleEngine 实例
            csv_sources: CSV 源信息，格式为 {source_name: {path, skip_header}}
        """
        self.engine = engine
        self.csv_sources = csv_sources
        self.watcher = CSVWatcher()

    def setup_watching(self):
        """设置文件监听"""
        for source_name, info in self.csv_sources.items():
            path = info['path']
            skip_header = info.get('skip_header', False)

            def make_callback(sn):
                def callback(source_name, new_data):
                    self.engine.push_event(sn, new_data)
                    self._show_outputs()
                return callback

            self.watcher.watch(path, source_name, make_callback(source_name), skip_header)

    def _show_outputs(self):
        """显示当前输出"""
        outputs = self.engine.get_sink_outputs()
        print("\n当前输出：")
        print("-" * 60)
        for name, value in outputs.items():
            # 截断过长的输出
            value_str = str(value)
            if len(value_str) > 80:
                value_str = value_str[:77] + "..."
            print(f"  {name} = {value_str}")
        print("-" * 60)

    def start(self):
        """启动监听"""
        self.watcher.start()

    def stop(self):
        """停止监听"""
        self.watcher.stop()


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import sys

    # 简单测试
    def test_callback(source_name, data):
        print(f"回调: {source_name} 更新为 {len(data)} 行")

    watcher = CSVWatcher()
    watcher.watch("examples/test_data.csv", "data", test_callback, skip_header=True)

    print("开始监听 examples/test_data.csv")
    print("请修改该文件并保存，观察输出")
    print("按 Ctrl+C 退出")

    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收到中断信号")
    finally:
        watcher.stop()
