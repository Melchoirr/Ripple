#!/usr/bin/env python3
"""
Ripple Language - Interactive Runner
交互式运行器，可以执行 .rpl 文件并进行交互式输入
"""

import sys
import argparse
from ripple_compiler import RippleCompiler
from ripple_engine import RippleEngine


class RippleRunner:
    """Ripple 交互式运行器"""

    def __init__(self, filename: str):
        self.filename = filename
        self.compiler = RippleCompiler()
        self.engine: RippleEngine = None

    def load_and_compile(self):
        """加载并编译 Ripple 文件"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                source_code = f.read()

            print(f"正在编译 {self.filename}...")
            print("=" * 80)

            self.engine = self.compiler.run(source_code)

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

    def interactive_mode(self):
        """交互式模式"""
        print("\n进入交互模式（输入 'help' 查看帮助，'quit' 退出）")
        print("=" * 80)

        # 显示所有源节点
        sources = [name for name, node in self.engine.nodes.items() if node.is_source]
        if sources:
            print(f"\n可用的源节点: {', '.join(sources)}")

        self.show_outputs()

        while True:
            try:
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("退出...")
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

    args = parser.parse_args()

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
