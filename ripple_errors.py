"""
Ripple Language - Error Handling (错误处理)
定义完整的错误类型和错误处理机制
"""

from typing import List, Optional, Set
from dataclasses import dataclass


class RippleError(Exception):
    """Ripple 错误基类"""
    def __init__(self, message: str, line: Optional[int] = None, column: Optional[int] = None):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.line is not None and self.column is not None:
            return f"Error at line {self.line}, column {self.column}: {self.message}"
        elif self.line is not None:
            return f"Error at line {self.line}: {self.message}"
        else:
            return f"Error: {self.message}"


# ==================== 词法/语法错误 ====================

class LexicalError(RippleError):
    """词法分析错误"""
    pass


class SyntaxError(RippleError):
    """语法分析错误"""
    pass


class ParseError(RippleError):
    """解析错误"""
    pass


# ==================== 编译错误 ====================

class CompileError(RippleError):
    """编译错误基类"""
    pass


class CircularDependencyError(CompileError):
    """循环依赖错误"""
    def __init__(self, cycle_path: List[str], line: Optional[int] = None):
        self.cycle_path = cycle_path
        cycle_str = " -> ".join(cycle_path)
        message = f"Circular dependency detected: {cycle_str}"
        super().__init__(message, line)


class UndefinedReferenceError(CompileError):
    """未定义引用错误"""
    def __init__(self, name: str, referenced_in: str, line: Optional[int] = None):
        self.name = name
        self.referenced_in = referenced_in
        message = f"Undefined reference '{name}' in '{referenced_in}'"
        super().__init__(message, line)


class DuplicateDefinitionError(CompileError):
    """重复定义错误"""
    def __init__(self, name: str, first_line: Optional[int] = None, second_line: Optional[int] = None):
        self.name = name
        if first_line and second_line:
            message = f"Duplicate definition of '{name}' (first defined at line {first_line}, redefined at line {second_line})"
        else:
            message = f"Duplicate definition of '{name}'"
        super().__init__(message, second_line)


class TypeError(CompileError):
    """类型错误"""
    def __init__(self, expected: str, actual: str, context: str, line: Optional[int] = None):
        self.expected = expected
        self.actual = actual
        self.context = context
        message = f"Type error in {context}: expected {expected}, but got {actual}"
        super().__init__(message, line)


class InvalidPreUsageError(CompileError):
    """非法的 Pre 操作符使用"""
    def __init__(self, stream_name: str, line: Optional[int] = None):
        message = f"Invalid use of 'pre': stream '{stream_name}' must reference itself or another stream"
        super().__init__(message, line)


# ==================== 运行时错误 ====================

class RuntimeError(RippleError):
    """运行时错误基类"""
    pass


class SourceNotFoundError(RuntimeError):
    """源节点未找到"""
    def __init__(self, source_name: str):
        message = f"Source '{source_name}' not found"
        super().__init__(message)


class NodeNotFoundError(RuntimeError):
    """节点未找到"""
    def __init__(self, node_name: str):
        message = f"Node '{node_name}' not found in dependency graph"
        super().__init__(message)


class EvaluationError(RuntimeError):
    """求值错误"""
    def __init__(self, node_name: str, original_error: Exception):
        self.node_name = node_name
        self.original_error = original_error
        message = f"Error evaluating node '{node_name}': {str(original_error)}"
        super().__init__(message)


class DivisionByZeroError(RuntimeError):
    """除零错误"""
    def __init__(self, node_name: str):
        message = f"Division by zero in node '{node_name}'"
        super().__init__(message)


# ==================== 错误诊断工具 ====================

@dataclass
class ErrorContext:
    """错误上下文信息"""
    source_code: str
    line: int
    column: int

    def get_line_context(self, before: int = 2, after: int = 2) -> str:
        """获取错误行的上下文"""
        lines = self.source_code.split('\n')
        start = max(0, self.line - before - 1)
        end = min(len(lines), self.line + after)

        context_lines = []
        for i in range(start, end):
            line_num = i + 1
            line_content = lines[i]
            marker = ">>> " if line_num == self.line else "    "
            context_lines.append(f"{marker}{line_num:4d} | {line_content}")

            # 添加错误指示符
            if line_num == self.line and self.column > 0:
                spaces = " " * (self.column + 10)  # 10 = len(">>> ") + len("1234 | ")
                context_lines.append(f"{spaces}^")

        return "\n".join(context_lines)


class CircularDependencyDetector:
    """循环依赖检测器 - 增强版"""

    def __init__(self):
        self.visited: Set[str] = set()
        self.rec_stack: List[str] = []  # 递归栈，用于追踪路径

    def detect_cycle(self, deps_graph: dict, start_node: str) -> Optional[List[str]]:
        """
        检测从 start_node 开始的循环依赖
        返回循环路径，如果没有循环则返回 None
        """
        if start_node in self.visited:
            return None

        if start_node in self.rec_stack:
            # 找到循环，返回循环路径
            cycle_start_idx = self.rec_stack.index(start_node)
            return self.rec_stack[cycle_start_idx:] + [start_node]

        self.rec_stack.append(start_node)

        if start_node in deps_graph:
            for dep in deps_graph[start_node]:
                cycle = self.detect_cycle(deps_graph, dep)
                if cycle:
                    return cycle

        self.rec_stack.pop()
        self.visited.add(start_node)
        return None

    def find_all_cycles(self, deps_graph: dict) -> List[List[str]]:
        """查找所有循环依赖"""
        cycles = []
        self.visited = set()

        for node in deps_graph:
            self.rec_stack = []
            cycle = self.detect_cycle(deps_graph, node)
            if cycle and cycle not in cycles:
                cycles.append(cycle)

        return cycles


class UndefinedReferenceChecker:
    """未定义引用检查器"""

    @staticmethod
    def check(stream_decls: list, source_names: Set[str]) -> List[UndefinedReferenceError]:
        """检查所有未定义的引用"""
        errors = []
        defined_names = source_names.copy()

        # 首先收集所有流的名字
        for decl in stream_decls:
            defined_names.add(decl.name)

        # 检查每个流的依赖
        for decl in stream_decls:
            for dep in decl.static_dependencies:
                if not UndefinedReferenceChecker._is_defined(dep, defined_names):
                    errors.append(
                        UndefinedReferenceError(dep, decl.name)
                    )

        return errors

    @staticmethod
    def _is_defined(dep: str, defined_names: Set[str]) -> bool:
        """检查依赖是否已定义

        对于带点的依赖（如 stats.count），检查：
        1. 完整路径是否已定义（如 p.x 作为展开的源节点）
        2. 或者基础名称是否已定义（如 stats 是一个返回结构体的流）
        """
        # 直接匹配
        if dep in defined_names:
            return True

        # 对于带点的引用，检查基础名称
        if '.' in dep:
            base_name = dep.split('.')[0]
            if base_name in defined_names:
                return True

        return False


class DuplicateDefinitionChecker:
    """重复定义检查器"""

    @staticmethod
    def check(all_decls: list) -> List[DuplicateDefinitionError]:
        """检查重复定义"""
        errors = []
        seen_names = {}

        for decl in all_decls:
            name = decl.name
            if name in seen_names:
                errors.append(
                    DuplicateDefinitionError(name)
                )
            else:
                seen_names[name] = decl

        return errors


# ==================== 错误报告器 ====================

class ErrorReporter:
    """错误报告器 - 提供友好的错误信息"""

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.errors: List[RippleError] = []

    def add_error(self, error: RippleError):
        """添加错误"""
        self.errors.append(error)

    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0

    def report(self) -> str:
        """生成错误报告"""
        if not self.errors:
            return "No errors"

        report_lines = [
            "=" * 80,
            f"Compilation failed with {len(self.errors)} error(s):",
            "=" * 80,
            ""
        ]

        for i, error in enumerate(self.errors, 1):
            report_lines.append(f"[{i}] {error._format_message()}")

            # 如果有行号，显示上下文
            if error.line is not None:
                context = ErrorContext(self.source_code, error.line, error.column or 0)
                report_lines.append("\nContext:")
                report_lines.append(context.get_line_context())

            report_lines.append("")

        report_lines.append("=" * 80)
        return "\n".join(report_lines)

    def print_report(self):
        """打印错误报告"""
        print(self.report())

    def raise_if_errors(self):
        """如果有错误，抛出异常"""
        if self.has_errors():
            raise CompileError(f"\n{self.report()}")


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 测试循环依赖检测
    print("测试 1: 循环依赖检测")
    print("=" * 80)

    deps_graph = {
        'A': {'B'},
        'B': {'C'},
        'C': {'A'},  # 循环: A -> B -> C -> A
        'D': {'E'},
        'E': set()
    }

    detector = CircularDependencyDetector()
    cycles = detector.find_all_cycles(deps_graph)

    if cycles:
        print(f"发现 {len(cycles)} 个循环依赖:")
        for cycle in cycles:
            print(f"  {' -> '.join(cycle)}")
    else:
        print("未发现循环依赖")

    print("\n" + "=" * 80)
    print("\n测试 2: 错误报告")
    print("=" * 80)

    source_code = """
source A : int := 1;
stream B <- A * 2;
stream C <- B + D;  // D 未定义
stream E <- C + 1;
"""

    reporter = ErrorReporter(source_code)
    reporter.add_error(UndefinedReferenceError("D", "C", line=3))
    reporter.add_error(CircularDependencyError(["A", "B", "C", "A"], line=4))

    reporter.print_report()
