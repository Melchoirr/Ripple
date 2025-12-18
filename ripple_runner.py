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
        self.source_code: str = ""  # 保存源代码用于 AST 可视化
        self.csv_sources: Dict[str, Dict] = {}  # CSV 源信息
        self.watcher: CSVWatcher = None  # CSV 文件监听器
        self.watching: bool = False  # 是否正在监听

    def load_and_compile(self):
        """加载并编译 Ripple 文件"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                self.source_code = f.read()

            print(f"正在编译 {self.filename}...")
            print("=" * 80)

            self.engine = self.compiler.run(self.source_code)

            # 获取 CSV 源信息
            self.csv_sources = self.compiler.csv_sources
            if self.csv_sources:
                print(f"\n检测到 {len(self.csv_sources)} 个 CSV 数据源:")
                for name, info in self.csv_sources.items():
                    print(f"  {name} <- {info['path']}")

            print("\n✓ 编译成功！")
            return True

        except FileNotFoundError:
            print(f"错误: 文件 '{self.filename}' 不存在")
            return False
        except Exception as e:
            print(f"编译错误: {e}")
            import traceback
            traceback.print_exc()
            return False

    def show_graph(self):
        """显示依赖图"""
        print("\n" + "=" * 80)
        self.engine.print_graph()

    def show_outputs(self):
        """显示当前输出"""
        outputs = self.engine.get_sink_outputs()
        print("\n当前输出：")
        print("-" * 80)
        for name, value in outputs.items():
            print(f"  {name} = {value}")
        print("-" * 80)

    def setup_watcher(self):
        """设置 CSV 文件监听"""
        if not self.csv_sources:
            return

        self.watcher = CSVWatcher()

        for source_name, info in self.csv_sources.items():
            path = info['path']
            skip_header = info.get('skip_header', False)

            # 使用当前工作目录解析相对路径（与 load_csv 一致）
            if not os.path.isabs(path):
                path = os.path.abspath(path)

            print(f"  监听文件: {path}")

            # 创建回调函数
            def make_callback(sn):
                def callback(_source_name, new_data):
                    self.engine.push_event(sn, new_data)
                    self.show_outputs()
                return callback

            self.watcher.watch(path, source_name, make_callback(source_name), skip_header)

    def start_watching(self):
        """启动文件监听"""
        if not self.csv_sources:
            print("没有 CSV 数据源需要监听")
            return

        if self.watching:
            print("文件监听已经在运行")
            return

        if self.watcher is None:
            self.setup_watcher()

        self.watcher.start()
        self.watching = True

    def stop_watching(self):
        """停止文件监听"""
        if not self.watching:
            return

        if self.watcher:
            self.watcher.stop()
        self.watching = False

    def interactive_mode(self):
        """交互式模式"""
        print("\n进入交互模式（输入 'help' 查看帮助，'quit' 退出）")
        print("=" * 80)

        # 显示所有源节点
        sources = [name for name, node in self.engine.nodes.items() if node.is_source]
        if sources:
            print(f"\n可用的源节点: {', '.join(sources)}")

        # 显示 CSV 源提示
        if self.csv_sources:
            print(f"\n提示: 检测到 CSV 数据源，输入 'watch' 开启文件监听自动更新")

        self.show_outputs()

        while True:
            try:
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("退出...")
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

                if user_input.lower() == 'watch':
                    if self.watching:
                        self.stop_watching()
                    else:
                        self.start_watching()
                    continue

                if user_input.lower() == 'ast':
                    print("\n" + visualize_ast(self.source_code, "tree"))
                    continue

                if user_input.lower().startswith('ast '):
                    fmt = user_input[4:].strip().lower()
                    if fmt in ['tree', 'dot', 'json']:
                        result = visualize_ast(self.source_code, fmt)
                        print("\n" + result)
                        if fmt == 'dot':
                            output_file = self.filename.replace('.rpl', '_ast.dot')
                            save_dot_file(self.source_code, output_file)
                    else:
                        print("错误: 格式应为 tree, dot 或 json")
                    continue

                # 解析输入：source_name = value
                if '=' in user_input:
                    parts = user_input.split('=')
                    if len(parts) == 2:
                        source_name = parts[0].strip()
                        value_str = parts[1].strip()

                        if source_name not in sources:
                            print(f"错误: '{source_name}' 不是有效的源节点")
                            continue

                        # 尝试解析值
                        try:
                            # 尝试整数
                            value = int(value_str)
                        except ValueError:
                            try:
                                # 尝试浮点数
                                value = float(value_str)
                            except ValueError:
                                # 字符串或布尔值
                                if value_str.lower() == 'true':
                                    value = True
                                elif value_str.lower() == 'false':
                                    value = False
                                else:
                                    # 去掉引号的字符串
                                    value = value_str.strip('"\'')

                        # 推送事件
                        print(f"\n推送事件: {source_name} = {value}")
                        self.engine.push_event(source_name, value)

                        # 显示输出
                        self.show_outputs()
                    else:
                        print("错误: 输入格式应为 'source_name = value'")
                else:
                    print("错误: 输入格式应为 'source_name = value'")
                    print("输入 'help' 查看帮助")

            except KeyboardInterrupt:
                print("\n\n收到中断信号，退出...")
                self.stop_watching()
                break
            except Exception as e:
                print(f"错误: {e}")

    def show_help(self):
        """显示帮助信息"""
        print("\n" + "=" * 80)
        print("Ripple 交互式运行器 - 帮助")
        print("=" * 80)
        print("\n命令:")
        print("  source_name = value  - 向源节点推送值")
        print("  graph                - 显示依赖图结构")
        print("  outputs              - 显示当前所有输出")
        print("  sources              - 列出所有源节点")
        print("  watch                - 开启/关闭 CSV 文件监听（自动更新）")
        print("  ast                  - 显示 AST (树形)")
        print("  ast tree             - 显示 AST (树形)")
        print("  ast dot              - 显示 AST (Graphviz DOT) 并保存文件")
        print("  ast json             - 显示 AST (JSON)")
        print("  help                 - 显示此帮助信息")
        print("  quit/exit/q          - 退出程序")
        print("\n值类型:")
        print("  整数: 42")
        print("  浮点数: 3.14")
        print("  布尔值: true, false")
        print("  字符串: \"hello\" 或 hello")
        print("\n示例:")
        print("  > A = 5")
        print("  > temperature = 25.5")
        print("  > enabled = true")
        print("=" * 80)

    def run(self):
        """运行 Ripple 程序"""
        if not self.load_and_compile():
            return 1

        self.show_graph()
        self.interactive_mode()

        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Ripple Language Interactive Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python ripple_runner.py examples/example1_diamond.rpl
  python ripple_runner.py examples/example3_fold.rpl

然后在交互模式中输入：
  > A = 5
  > numbers = 10
        """
    )

    parser.add_argument('filename', help='Ripple 源文件 (.rpl)')
    parser.add_argument('-g', '--graph', action='store_true',
                       help='显示依赖图后退出（不进入交互模式）')
    parser.add_argument('--ast', choices=['tree', 'dot', 'json'],
                       help='显示 AST 后退出 (tree/dot/json)')

    args = parser.parse_args()

    # AST 可视化模式
    if args.ast:
        try:
            with open(args.filename, 'r', encoding='utf-8') as f:
                source_code = f.read()
            result = visualize_ast(source_code, args.ast)
            print(result)
            if args.ast == 'dot':
                output_file = args.filename.replace('.rpl', '_ast.dot')
                save_dot_file(source_code, output_file)
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
