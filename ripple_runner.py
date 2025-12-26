#!/usr/bin/env python3
"""
Ripple Language - Interactive Runner
交互式运行器，可以执行 .rpl 文件并进行交互式输入
"""

import sys
import os
import argparse
from typing import Dict
from ripple_compiler import RippleCompiler
from ripple_engine import RippleEngine
from ripple_ast_visualizer import visualize_ast, save_dot_file
from ripple_watcher import CSVWatcher


class RippleRunner:
    """Ripple 交互式运行器"""

    def __init__(self, filename: str):
        self.filename = filename
        self.compiler = RippleCompiler()
        self.engine: RippleEngine = None
        self.source_code: str = ""
        self.csv_sources: Dict[str, Dict] = {}
        self.watcher: CSVWatcher = None

    def load_and_compile(self):
        """加载并编译 Ripple 文件"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                self.source_code = f.read()

            self.engine = self.compiler.run(self.source_code)
            self.csv_sources = self.compiler.csv_sources

            # 自动启动 CSV 文件监听
            if self.csv_sources:
                self._setup_and_start_watcher()

            return True

        except FileNotFoundError:
            print(f"错误: 文件 '{self.filename}' 不存在")
            return False
        except Exception as e:
            print(f"编译错误: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _setup_and_start_watcher(self):
        """设置并启动 CSV 文件监听"""
        self.watcher = CSVWatcher()

        for source_name, info in self.csv_sources.items():
            path = info['path']
            skip_header = info.get('skip_header', False)

            if not os.path.isabs(path):
                path = os.path.abspath(path)

            def make_callback(sn):
                def callback(_source_name, new_data):
                    self.engine.push_event(sn, new_data)
                    self.show_outputs()
                return callback

            self.watcher.watch(path, source_name, make_callback(source_name), skip_header)

        self.watcher.start()

    def stop_watching(self):
        """停止文件监听"""
        if self.watcher:
            self.watcher.stop()

    def show_graph(self):
        """显示依赖图"""
        self.engine.print_graph()

    def show_outputs(self):
        """显示当前输出"""
        outputs = self.engine.get_sink_outputs()
        for name, value in outputs.items():
            print(f"{name} = {value}")

    def interactive_mode(self):
        """交互式模式"""
        sources = [name for name, node in self.engine.nodes.items() if node.is_source]

        self.show_outputs()

        while True:
            try:
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    self.stop_watching()
                    break

                if user_input.lower() == 'help':
                    self.show_help()
                    continue

                if user_input.lower() == 'graph':
                    self.show_graph()
                    continue

                if user_input.lower() == 'outputs':
                    self.show_outputs()
                    continue

                if user_input.lower() == 'sources':
                    print(f"可用的源节点: {', '.join(sources)}")
                    continue

                if user_input.lower() == 'ast':
                    print(visualize_ast(self.source_code, "tree"))
                    continue

                if user_input.lower().startswith('ast '):
                    fmt = user_input[4:].strip().lower()
                    if fmt in ['tree', 'dot', 'json']:
                        result = visualize_ast(self.source_code, fmt)
                        print(result)
                        if fmt == 'dot':
                            output_file = self.filename.replace('.rpl', '_ast.dot')
                            save_dot_file(self.source_code, output_file)
                    else:
                        print("格式应为 tree, dot 或 json")
                    continue

                # 解析输入：source_name = value
                if '=' in user_input:
                    parts = user_input.split('=')
                    if len(parts) == 2:
                        source_name = parts[0].strip()
                        value_str = parts[1].strip()

                        if source_name not in sources:
                            print(f"'{source_name}' 不是有效的源节点")
                            continue

                        # 解析值
                        try:
                            value = int(value_str)
                        except ValueError:
                            try:
                                value = float(value_str)
                            except ValueError:
                                if value_str.lower() == 'true':
                                    value = True
                                elif value_str.lower() == 'false':
                                    value = False
                                else:
                                    value = value_str.strip('"\'')

                        self.engine.push_event(source_name, value)
                        self.show_outputs()
                    else:
                        print("格式: source = value")
                else:
                    print("格式: source = value")

            except KeyboardInterrupt:
                print("\n")
                self.stop_watching()
                break
            except Exception as e:
                print(f"错误: {e}")

    def show_help(self):
        """显示帮助信息"""
        print("""
命令:
  source = value  - 推送值到源节点
  graph           - 显示依赖图
  outputs         - 显示输出
  sources         - 列出源节点
  ast [tree|dot|json] - 显示 AST
  quit            - 退出
""")

    def run(self):
        """运行 Ripple 程序"""
        if not self.load_and_compile():
            return 1

        self.interactive_mode()
        return 0


def main():
    parser = argparse.ArgumentParser(description='Ripple Language Runner')
    parser.add_argument('filename', help='Ripple 源文件 (.rpl)')
    parser.add_argument('-g', '--graph', action='store_true', help='显示依赖图后退出')
    parser.add_argument('--ast', choices=['tree', 'dot', 'json'], help='显示 AST 后退出')

    args = parser.parse_args()

    if args.ast:
        try:
            with open(args.filename, 'r', encoding='utf-8') as f:
                source_code = f.read()
            print(visualize_ast(source_code, args.ast))
            if args.ast == 'dot':
                save_dot_file(source_code, args.filename.replace('.rpl', '_ast.dot'))
            return 0
        except Exception as e:
            print(f"错误: {e}")
            return 1

    runner = RippleRunner(args.filename)

    if args.graph:
        if runner.load_and_compile():
            runner.show_graph()
            runner.show_outputs()
            return 0
        return 1

    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
