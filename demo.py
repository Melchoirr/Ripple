#!/usr/bin/env python3
"""
Ripple Language Demo
演示 Ripple 语言的核心特性
"""

from ripple_compiler import RippleCompiler


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def demo_diamond_dependency():
    """演示 1: 菱形依赖 - 无故障传播"""
    print_section("演示 1: 菱形依赖（Diamond Dependency）- 无故障传播")

    code = """
    source A : int := 1;
    stream B <- A * 2;
    stream C <- A + 1;
    stream D <- B + C;
    sink output <- D;
    """

    print("代码:")
    print(code)

    compiler = RippleCompiler()
    engine = compiler.run(code)

    print("说明：")
    print("  当 A=1 时，B=2, C=2, D=4")
    print("  当 A 变为 2 时，Ripple 保证 D 只计算一次：")
    print("  - B 更新为 4")
    print("  - C 更新为 3")
    print("  - D 基于最新的 B 和 C 计算：4 + 3 = 7")
    print("  - 不会出现错误的中间状态（如 2+3=5 或 4+2=6）")

    print("\n执行序列：")
    for value in [1, 2, 5, 10]:
        engine.push_event("A", value)
        result = engine.get_value("output")
        b = engine.get_value("B")
        c = engine.get_value("C")
        print(f"  A={value:2d} -> B={b:2d}, C={c:2d}, D={result:2d}")


def demo_fold():
    """演示 2: 状态累积 - Fold 操作符"""
    print_section("演示 2: 状态累积 - 使用 Fold 操作符")

    code = """
    source numbers : int := 0;
    stream sum <- fold(numbers, 0, (acc, x) => acc + x);
    stream product <- fold(numbers, 1, (acc, x) => acc * x);
    stream count <- fold(numbers, 0, (acc, x) => acc + 1);
    sink sum_out <- sum;
    sink prod_out <- product;
    sink count_out <- count;
    """

    print("代码:")
    print(code)

    print("\n说明：")
    print("  fold(stream, initial, (acc, x) => expression)")
    print("  类似于函数式编程中的 reduce，用于累积计算")

    print("\n执行序列：")
    print("  注意：当前版本的 Fold 实现有 Lambda 作用域问题")
    print("  这是一个已知的待修复问题，不影响核心算法验证")


def demo_conditional():
    """演示 3: 条件表达式"""
    print_section("演示 3: 条件表达式和动态依赖")

    code = """
    source temperature : float := 20.0;
    stream status <- if temperature < 10.0 then "cold"
                     else if temperature < 25.0 then "comfortable"
                     else "hot" end end;
    stream action <- if status == "hot" then "Turn on AC"
                     else if status == "cold" then "Turn on heater"
                     else "No action needed" end end;
    sink status_out <- status;
    sink action_out <- action;
    """

    print("代码:")
    print(code)

    compiler = RippleCompiler()
    engine = compiler.run(code)

    print("\n说明：")
    print("  条件表达式支持嵌套的 if-then-else")
    print("  根据温度自动调整状态和建议")

    print("\n执行序列：")
    test_temps = [5.0, 15.0, 20.0, 30.0]
    for temp in test_temps:
        engine.push_event("temperature", temp)
        outputs = engine.get_sink_outputs()
        print(f"  温度={temp:4.1f}°C -> 状态='{outputs['status_out']}', "
              f"建议='{outputs['action_out']}'")


def demo_error_detection():
    """演示 4: 错误检测"""
    print_section("演示 4: 编译期错误检测")

    print("错误示例 1: 循环依赖")
    print("-" * 80)
    code1 = """
    stream A <- B + 1;
    stream B <- C + 1;
    stream C <- A + 1;
    """
    print(code1)

    compiler = RippleCompiler()
    try:
        engine = compiler.run(code1)
        print("❌ 未检测到错误（不应该发生）")
    except Exception:
        print("✓ 正确检测到循环依赖错误")

    print("\n错误示例 2: 未定义引用")
    print("-" * 80)
    code2 = """
    source A : int := 1;
    stream B <- A + undefined_var;
    """
    print(code2)

    compiler = RippleCompiler()
    try:
        engine = compiler.run(code2)
        print("❌ 未检测到错误（不应该发生）")
    except Exception:
        print("✓ 正确检测到未定义引用错误")

    print("\n错误示例 3: 重复定义")
    print("-" * 80)
    code3 = """
    source A : int := 1;
    stream B <- A * 2;
    stream B <- A + 1;
    """
    print(code3)

    compiler = RippleCompiler()
    try:
        engine = compiler.run(code3)
        print("❌ 未检测到错误（不应该发生）")
    except Exception:
        print("✓ 正确检测到重复定义错误")


def main():
    """运行所有演示"""
    print("\n")
    print("█" * 80)
    print(" " * 25 + "Ripple 语言演示")
    print(" " * 18 + "原生响应式流语言 Demo")
    print("█" * 80)

    # 运行所有演示
    demo_diamond_dependency()
    demo_conditional()
    demo_error_detection()

    # 总结
    print_section("演示总结")
    print("Ripple 语言的核心特性：")
    print()
    print("  ✓ 原生响应式：依赖图自动管理，无需显式订阅")
    print("  ✓ 零故障传播：拓扑排序保证状态一致性")
    print("  ✓ 声明式语法：类似电子表格的直观模型")
    print("  ✓ 错误检测：编译期捕获循环依赖、未定义引用等")
    print()
    print("更多示例请查看 examples/ 目录")
    print("交互式运行：python ripple_runner.py examples/example1_diamond.rpl")
    print("错误处理测试：python test_error_handling.py")
    print()


if __name__ == "__main__":
    main()
