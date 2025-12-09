#!/usr/bin/env python3
"""
Ripple 语言 - 错误处理测试套件
全面测试编译器的错误检测能力
"""

from ripple_compiler import RippleCompiler
from ripple_errors import CircularDependencyError, UndefinedReferenceError, DuplicateDefinitionError


def print_test_header(test_num: int, title: str):
    """打印测试标题"""
    print("\n" + "=" * 80)
    print(f"测试 {test_num}: {title}")
    print("=" * 80 + "\n")


def run_test(code: str, should_fail: bool = False, expected_error: str = None):
    """运行单个测试"""
    print("代码:")
    print("-" * 80)
    print(code)
    print("-" * 80 + "\n")

    compiler = RippleCompiler()
    try:
        engine = compiler.run(code)

        if should_fail:
            print("❌ 测试失败：预期应该报错，但编译成功了")
            return False
        else:
            print("✓ 测试通过：编译成功")
            return True

    except Exception as e:
        if should_fail:
            error_msg = str(e)
            if expected_error and expected_error in error_msg:
                print(f"✓ 测试通过：正确检测到错误")
                print(f"  预期错误类型: {expected_error}")
                return True
            elif expected_error:
                print(f"❌ 测试失败：检测到错误，但类型不符")
                print(f"  预期: {expected_error}")
                print(f"  实际: {error_msg[:100]}...")
                return False
            else:
                print(f"✓ 测试通过：正确检测到错误")
                return True
        else:
            print(f"❌ 测试失败：不应该报错，但发生了错误")
            print(f"  错误信息: {str(e)[:200]}...")
            return False


def main():
    """运行所有测试"""
    print("\n" + "█" * 80)
    print(" " * 20 + "Ripple 错误处理测试套件")
    print(" " * 25 + "Error Handling Tests")
    print("█" * 80)

    passed = 0
    total = 0

    # ========== 正确代码测试 ==========

    print_test_header(1, "正确的菱形依赖")
    total += 1
    code = """
    source A : int := 1;
    stream B <- A * 2;
    stream C <- A + 1;
    stream D <- B + C;
    sink output <- D;
    """
    if run_test(code, should_fail=False):
        passed += 1

    print_test_header(2, "正确的自引用（使用 Pre）")
    total += 1
    code = """
    source tick : int := 0;
    stream counter <- pre(counter, 0) + 1;
    sink output <- counter;
    """
    if run_test(code, should_fail=False):
        passed += 1

    print_test_header(3, "复杂的多层依赖")
    total += 1
    code = """
    source input : int := 10;
    stream layer1a <- input * 2;
    stream layer1b <- input + 5;
    stream layer2a <- layer1a + layer1b;
    stream layer2b <- layer1a * layer1b;
    stream result <- layer2a + layer2b;
    sink output <- result;
    """
    if run_test(code, should_fail=False):
        passed += 1

    # ========== 循环依赖错误测试 ==========

    print_test_header(4, "简单循环依赖 (A -> B -> A)")
    total += 1
    code = """
    source X : int := 1;
    stream A <- B + 1;
    stream B <- A + 1;
    sink output <- B;
    """
    if run_test(code, should_fail=True, expected_error="Circular dependency"):
        passed += 1

    print_test_header(5, "三角循环依赖 (A -> B -> C -> A)")
    total += 1
    code = """
    stream A <- B + 1;
    stream B <- C + 1;
    stream C <- A + 1;
    sink output <- C;
    """
    if run_test(code, should_fail=True, expected_error="Circular dependency"):
        passed += 1

    print_test_header(6, "复杂循环依赖")
    total += 1
    code = """
    source X : int := 1;
    stream A <- X + 1;
    stream B <- A + C;
    stream C <- D + 1;
    stream D <- B + 1;
    sink output <- D;
    """
    if run_test(code, should_fail=True, expected_error="Circular dependency"):
        passed += 1

    # ========== 未定义引用错误测试 ==========

    print_test_header(7, "未定义的变量")
    total += 1
    code = """
    source A : int := 1;
    stream B <- A * 2;
    stream C <- B + undefined_var;
    sink output <- C;
    """
    if run_test(code, should_fail=True, expected_error="Undefined reference"):
        passed += 1

    print_test_header(8, "多个未定义引用")
    total += 1
    code = """
    source A : int := 1;
    stream B <- A + X;
    stream C <- B + Y;
    stream D <- C + Z;
    sink output <- D;
    """
    if run_test(code, should_fail=True, expected_error="Undefined reference"):
        passed += 1

    print_test_header(9, "拼写错误导致的未定义引用")
    total += 1
    code = """
    source temperature : float := 25.0;
    stream fahrenheit <- temperatur * 9.0 / 5.0 + 32.0;
    sink output <- fahrenheit;
    """
    if run_test(code, should_fail=True, expected_error="Undefined reference"):
        passed += 1

    # ========== 重复定义错误测试 ==========

    print_test_header(10, "重复的流定义")
    total += 1
    code = """
    source A : int := 1;
    stream B <- A * 2;
    stream B <- A + 1;
    sink output <- B;
    """
    if run_test(code, should_fail=True, expected_error="Duplicate definition"):
        passed += 1

    print_test_header(11, "源和流同名")
    total += 1
    code = """
    source A : int := 1;
    stream A <- A * 2;
    sink output <- A;
    """
    if run_test(code, should_fail=True, expected_error="Duplicate definition"):
        passed += 1

    print_test_header(12, "多个重复定义")
    total += 1
    code = """
    source A : int := 1;
    stream B <- A * 2;
    stream C <- A + 1;
    stream B <- A * 3;
    stream C <- A + 2;
    sink output <- B;
    """
    if run_test(code, should_fail=True, expected_error="Duplicate definition"):
        passed += 1

    # ========== 边界情况测试 ==========

    print_test_header(13, "空依赖的流")
    total += 1
    code = """
    source A : int := 1;
    stream B <- 42;
    sink output <- B;
    """
    if run_test(code, should_fail=False):
        passed += 1

    print_test_header(14, "只有源节点")
    total += 1
    code = """
    source A : int := 1;
    source B : int := 2;
    sink output1 <- A;
    sink output2 <- B;
    """
    if run_test(code, should_fail=False):
        passed += 1

    print_test_header(15, "Fold 操作")
    total += 1
    code = """
    source numbers : int := 0;
    stream sum <- fold(numbers, 0, (acc, x) => acc + x);
    stream count <- fold(numbers, 0, (acc, x) => acc + 1);
    stream average <- sum / count;
    sink avg_output <- average;
    """
    if run_test(code, should_fail=False):
        passed += 1

    # ========== 结果统计 ==========

    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    print(f"\n总测试数: {total}")
    print(f"通过: {passed} ✓")
    print(f"失败: {total - passed} ✗")
    print(f"通过率: {passed / total * 100:.1f}%\n")

    if passed == total:
        print("🎉 所有测试通过！错误处理系统工作正常。")
    else:
        print(f"⚠️  有 {total - passed} 个测试失败，请检查。")

    print("=" * 80 + "\n")

    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
