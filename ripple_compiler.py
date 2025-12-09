"""
Ripple Language - Enhanced Compiler (增强版编译器)
集成完整的错误处理机制
"""

from typing import Dict, Any, Callable, Set, List
from ripple_ast import *
from ripple_parser import RippleParser
from ripple_lexer import RippleLexer
from ripple_engine import RippleEngine, ExpressionEvaluator
from ripple_errors import (
    CircularDependencyError,
    UndefinedReferenceError,
    DuplicateDefinitionError,
    CircularDependencyDetector,
    UndefinedReferenceChecker,
    DuplicateDefinitionChecker,
    ErrorReporter,
    CompileError
)


class RippleCompiler:
    """Ripple 编译器（带完整错误检查）"""

    def __init__(self):
        self.engine = RippleEngine()
        self.evaluator = ExpressionEvaluator(self.engine)
        self.source_code = ""
        self.error_reporter = None

    def compile(self, ast: Program):
        """编译程序（带错误检查）"""
        # 创建错误报告器
        self.error_reporter = ErrorReporter(self.source_code)

        # 1. 检查重复定义
        print("\n[编译阶段 1] 检查重复定义...")
        duplicate_errors = DuplicateDefinitionChecker.check(ast.statements)
        for error in duplicate_errors:
            self.error_reporter.add_error(error)

        # 如果有重复定义，立即报错
        if self.error_reporter.has_errors():
            self.error_reporter.print_report()
            self.error_reporter.raise_if_errors()

        # 2. 收集所有定义
        source_names = set()
        stream_decls = []

        for stmt in ast.statements:
            if isinstance(stmt, SourceDecl):
                source_names.add(stmt.name)
            elif isinstance(stmt, StreamDecl):
                stream_decls.append(stmt)

        # 3. 检查未定义引用
        print("[编译阶段 2] 检查未定义引用...")
        undefined_errors = UndefinedReferenceChecker.check(stream_decls, source_names)
        for error in undefined_errors:
            self.error_reporter.add_error(error)

        # 如果有未定义引用，立即报错
        if self.error_reporter.has_errors():
            self.error_reporter.print_report()
            self.error_reporter.raise_if_errors()

        # 4. 检查循环依赖（增强版）
        print("[编译阶段 3] 检查循环依赖...")
        cycle_errors = self._detect_circular_dependencies(stream_decls)
        for error in cycle_errors:
            self.error_reporter.add_error(error)

        # 如果有循环依赖，立即报错
        if self.error_reporter.has_errors():
            self.error_reporter.print_report()
            self.error_reporter.raise_if_errors()

        # 5. 编译源声明
        print("[编译阶段 4] 编译源声明...")
        for stmt in ast.statements:
            if isinstance(stmt, SourceDecl):
                self._compile_source(stmt)

        # 6. 计算 rank 并编译流声明
        print("[编译阶段 5] 计算拓扑顺序...")
        self._compute_ranks(stream_decls)

        print("[编译阶段 6] 编译流声明...")
        for stmt in sorted(stream_decls, key=lambda s: s.rank):
            self._compile_stream(stmt)

        # 7. 编译 Sink 声明
        print("[编译阶段 7] 编译输出节点...")
        for stmt in ast.statements:
            if isinstance(stmt, SinkDecl):
                self._compile_sink(stmt)

        print("\n✓ 编译成功！无错误。\n")

    def _detect_circular_dependencies(self, stream_decls: List[StreamDecl]) -> List[CircularDependencyError]:
        """检测循环依赖（增强版）"""
        errors = []

        # 构建依赖图（过滤自引用）
        deps_graph: Dict[str, Set[str]] = {}
        for decl in stream_decls:
            # 过滤掉自引用（pre 操作符的情况）
            filtered_deps = {dep for dep in decl.static_dependencies if dep != decl.name}
            deps_graph[decl.name] = filtered_deps

        # 使用增强的循环检测器
        detector = CircularDependencyDetector()
        cycles = detector.find_all_cycles(deps_graph)

        for cycle in cycles:
            errors.append(CircularDependencyError(cycle))

        return errors

    def _compile_source(self, decl: SourceDecl):
        """编译源声明"""
        initial_value = None
        if decl.initial_value:
            try:
                initial_value = self.evaluator.evaluate(decl.initial_value, {})
            except Exception as e:
                raise CompileError(f"Error evaluating initial value for source '{decl.name}': {e}")

        self.engine.add_source(decl.name, initial_value)

    def _compile_stream(self, decl: StreamDecl):
        """编译流声明"""
        expr = decl.expression

        # 创建求值函数
        def formula(args):
            # 处理 Pre 操作符
            if isinstance(expr, PreOp):
                if expr.stream_name == decl.name:
                    # 自引用：返回当前值和更新状态
                    if '__state__' in args and args['__state__'] is not None:
                        prev_value = args['__state__']
                    else:
                        prev_value = self.evaluator.evaluate(expr.initial_value, {})

                    # 计算新值（这里简化为直接使用 prev_value + 其他计算）
                    # 实际应该进一步解析表达式
                    current_value = prev_value
                    return (current_value, current_value)
                else:
                    return self.evaluator.evaluate(expr, args)

            # 处理 Fold 操作符
            elif isinstance(expr, FoldOp):
                result = self.evaluator.evaluate(expr, args)
                return (result, result)

            # 普通表达式
            else:
                return self.evaluator.evaluate(expr, args)

        self.engine.add_stream(
            decl.name,
            formula,
            decl.static_dependencies,
            decl.is_stateful,
            None
        )

    def _compile_sink(self, decl: SinkDecl):
        """编译 Sink 声明"""
        expr = decl.expression
        dependencies = extract_dependencies(expr)

        def formula(args):
            return self.evaluator.evaluate(expr, args)

        self.engine.add_sink(decl.name, formula, dependencies)

    def _compute_ranks(self, stream_decls: List[StreamDecl]):
        """计算流声明的拓扑高度"""
        # 构建依赖图（移除自引用，因为 pre 操作符处理的是历史值）
        deps_graph: Dict[str, set] = {}
        for decl in stream_decls:
            # 过滤掉自引用依赖（使用 pre 的情况）
            filtered_deps = {dep for dep in decl.static_dependencies if dep != decl.name}
            deps_graph[decl.name] = filtered_deps

        # 拓扑排序计算 rank
        ranks: Dict[str, int] = {}
        visited: set = set()

        def compute_rank(name: str) -> int:
            if name in ranks:
                return ranks[name]

            if name in visited:
                # 这里不应该到达，因为已经做过循环检测
                raise CircularDependencyError([name])

            visited.add(name)

            if name not in deps_graph or not deps_graph[name]:
                # 源节点或无依赖节点
                ranks[name] = 0
                visited.remove(name)
                return 0

            max_dep_rank = 0
            for dep in deps_graph[name]:
                if dep in deps_graph:  # 只处理存在的依赖
                    dep_rank = compute_rank(dep)
                    max_dep_rank = max(max_dep_rank, dep_rank)

            rank = max_dep_rank + 1
            ranks[name] = rank
            visited.remove(name)
            return rank

        for decl in stream_decls:
            decl.rank = compute_rank(decl.name)

    def run(self, source_code: str) -> RippleEngine:
        """编译并返回引擎"""
        self.source_code = source_code

        try:
            # 词法分析
            print("\n[词法分析] 正在分析...")
            lexer = RippleLexer(source_code)
            tokens = lexer.tokenize()
            print(f"✓ 生成了 {len(tokens)} 个 tokens")

            # 语法分析
            print("\n[语法分析] 正在解析...")
            parser = RippleParser(tokens)
            ast = parser.parse()
            print(f"✓ 解析了 {len(ast.statements)} 个语句")

            # 编译
            print("\n[编译] 开始编译...")
            self.compile(ast)

            return self.engine

        except CompileError as e:
            print(f"\n✗ 编译失败:\n{str(e)}")
            raise
        except Exception as e:
            print(f"\n✗ 未预期的错误: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


# 测试代码
if __name__ == "__main__":
    print("=" * 80)
    print("测试 1: 正常的菱形依赖")
    print("=" * 80)

    code1 = """
    source A : int := 1;
    stream B <- A * 2;
    stream C <- A + 1;
    stream D <- B + C;
    sink output <- D;
    """

    compiler1 = RippleCompiler()
    try:
        engine1 = compiler1.run(code1)
        print("\n推送事件: A = 2")
        engine1.push_event("A", 2)
        print(f"输出: {engine1.get_sink_outputs()}")
    except Exception as e:
        print(f"错误: {e}")

    print("\n\n" + "=" * 80)
    print("测试 2: 循环依赖错误")
    print("=" * 80)

    code2 = """
    source A : int := 1;
    stream B <- C + 1;
    stream C <- D + 1;
    stream D <- B + 1;
    sink output <- D;
    """

    compiler2 = RippleCompiler()
    try:
        engine2 = compiler2.run(code2)
    except Exception as e:
        print(f"\n预期的错误已捕获")

    print("\n\n" + "=" * 80)
    print("测试 3: 未定义引用错误")
    print("=" * 80)

    code3 = """
    source A : int := 1;
    stream B <- A * 2;
    stream C <- B + X;
    sink output <- C;
    """

    compiler3 = RippleCompiler()
    try:
        engine3 = compiler3.run(code3)
    except Exception as e:
        print(f"\n预期的错误已捕获")

    print("\n\n" + "=" * 80)
    print("测试 4: 重复定义错误")
    print("=" * 80)

    code4 = """
    source A : int := 1;
    stream B <- A * 2;
    stream B <- A + 1;
    sink output <- B;
    """

    compiler4 = RippleCompiler()
    try:
        engine4 = compiler4.run(code4)
    except Exception as e:
        print(f"\n预期的错误已捕获")
