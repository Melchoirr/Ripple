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
from ripple_typechecker import TypeChecker


class RippleCompiler:
    """Ripple 编译器（带完整错误检查）"""

    def __init__(self):
        self.engine = RippleEngine()
        self.evaluator = ExpressionEvaluator(self.engine)
        self.source_code = ""
        self.error_reporter = None
        self.user_functions: Dict[str, FuncDecl] = {}  # 用户定义的函数
        self.type_defs: Dict[str, TypeNode] = {}  # 类型定义（如 type Point = {...}）
        self.type_checker = TypeChecker()  # 类型推断器
        self.csv_sources: Dict[str, Dict] = {}  # CSV 源信息 {source_name: {path, skip_header}}

    def compile(self, ast: Program):
        """编译程序（带错误检查）"""
        # 创建错误报告器
        self.error_reporter = ErrorReporter(self.source_code)

        # 0a. 编译类型定义（最先处理）
        print("\n[编译阶段 0a] 编译类型定义...")
        for stmt in ast.statements:
            if isinstance(stmt, TypeDecl):
                self._compile_type_decl(stmt)
        print(f"✓ 编译了 {len(self.type_defs)} 个类型定义")

        # 0b. 编译函数定义
        print("[编译阶段 0b] 编译函数定义...")
        for stmt in ast.statements:
            if isinstance(stmt, FuncDecl):
                self._compile_func(stmt)
        print(f"✓ 编译了 {len(self.user_functions)} 个用户函数")

        # 将用户函数传递给表达式求值器
        self.evaluator.user_functions = self.user_functions

        # 0c. 类型推断与检查
        print("[编译阶段 0c] 类型推断与检查...")
        self.type_checker.type_aliases = self.type_defs
        self.type_checker.user_functions = self.user_functions
        type_errors = self.type_checker.check_program(ast)
        if type_errors:
            for error in type_errors:
                print(f"  类型警告: {error}")
        # 显示推断的类型
        print(f"  推断的类型:")
        for name, type_node in self.type_checker.type_env.items():
            type_str = self._type_to_string(type_node)
            print(f"    {name}: {type_str}")
        print(f"✓ 类型检查完成，推断了 {len(self.type_checker.type_env)} 个类型")

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
                # 如果是结构体类型，也添加字段名
                # 先尝试显式类型，如果没有则从类型推断器获取
                type_sig = stmt.type_sig
                if type_sig is None:
                    type_sig = self.type_checker.get_type(stmt.name)
                struct_type = self._get_struct_type(type_sig)
                if struct_type:
                    for field_name in struct_type.fields.keys():
                        source_names.add(f"{stmt.name}.{field_name}")
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

        # 8. 触发初始传播（让所有有初始值的源节点传播到依赖节点）
        print("[编译阶段 8] 初始化所有节点值...")
        self._initialize_values(ast.statements)

        print("\n✓ 编译成功！无错误。\n")

    def _detect_circular_dependencies(self, stream_decls: List[StreamDecl]) -> List[CircularDependencyError]:
        """检测循环依赖（增强版）"""
        errors = []

        # 构建依赖图（过滤自引用，包含触发器）
        deps_graph: Dict[str, Set[str]] = {}
        for decl in stream_decls:
            # 过滤掉自引用（pre 操作符的情况）
            filtered_deps = {dep for dep in decl.static_dependencies if dep != decl.name}
            # 添加显式触发器
            if decl.trigger:
                filtered_deps.add(decl.trigger)
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

        # 检查是否是 load_csv 调用
        csv_info = self._extract_csv_info(decl.initial_value)
        if csv_info:
            # 记录 CSV 源信息用于文件监听
            self.csv_sources[decl.name] = csv_info

        if decl.initial_value:
            try:
                initial_value = self.evaluator.evaluate(decl.initial_value, {})
            except Exception as e:
                raise CompileError(f"Error evaluating initial value for source '{decl.name}': {e}")

        # 如果没有显式类型注解，从类型推断器获取推断的类型
        type_sig = decl.type_sig
        if type_sig is None:
            # 从类型推断器获取推断的类型
            inferred_type = self.type_checker.get_type(decl.name)
            if inferred_type:
                type_sig = inferred_type

        # 检查是否是结构体类型
        struct_type = self._get_struct_type(type_sig)

        if struct_type:
            # 结构体类型：展开为字段节点
            self._compile_struct_source(decl.name, struct_type, initial_value)
        else:
            # 普通类型
            self.engine.add_source(decl.name, initial_value)

    def _type_to_string(self, type_node: TypeNode) -> str:
        """将类型节点转换为可读字符串"""
        if type_node is None:
            return "unknown"
        if isinstance(type_node, BasicType):
            return type_node.name
        elif isinstance(type_node, ArrayType):
            elem_str = self._type_to_string(type_node.element_type)
            return f"[{elem_str}]"
        elif isinstance(type_node, StructType):
            fields_str = ", ".join(
                f"{k}: {self._type_to_string(v)}"
                for k, v in type_node.fields.items()
            )
            return f"{{{fields_str}}}"
        elif isinstance(type_node, FunctionType):
            params_str = ", ".join(self._type_to_string(p) for p in type_node.param_types)
            ret_str = self._type_to_string(type_node.return_type)
            return f"({params_str}) -> {ret_str}"
        else:
            return str(type_node)

    def _get_struct_type(self, type_sig: Optional[TypeNode]) -> Optional[StructType]:
        """获取结构体类型（如果是的话）"""
        if type_sig is None:
            return None
        if isinstance(type_sig, StructType):
            return type_sig
        elif isinstance(type_sig, BasicType):
            # 检查是否是自定义类型名
            if type_sig.name in self.type_defs:
                type_def = self.type_defs[type_sig.name]
                if isinstance(type_def, StructType):
                    return type_def
        return None

    def _compile_struct_source(self, name: str, struct_type: StructType, initial_value: Any):
        """编译结构体源（展开为字段节点）"""
        field_names = list(struct_type.fields.keys())

        # 1. 为每个字段创建独立的源节点
        for field_name in field_names:
            field_node_name = f"{name}.{field_name}"
            field_initial = None
            if initial_value and isinstance(initial_value, dict):
                field_initial = initial_value.get(field_name)
            self.engine.add_source(field_node_name, field_initial)

        # 2. 创建整体节点（虚拟节点，依赖所有字段）
        field_deps = {f"{name}.{f}" for f in field_names}

        def struct_formula(args):
            # 从字段节点重建结构体
            return {
                field_name: args.get(f"{name}.{field_name}")
                for field_name in field_names
            }

        self.engine.add_stream(name, struct_formula, field_deps)

    def _compile_type_decl(self, decl: TypeDecl):
        """编译类型定义"""
        if decl.name in self.type_defs:
            raise CompileError(f"Duplicate type definition: '{decl.name}'")
        self.type_defs[decl.name] = decl.type_def

    def _compile_func(self, decl: FuncDecl):
        """编译函数定义"""
        if decl.name in self.user_functions:
            raise CompileError(f"Duplicate function definition: '{decl.name}'")
        self.user_functions[decl.name] = decl

    def _compile_stream(self, decl: StreamDecl):
        """编译流声明"""
        expr = decl.expression

        # 创建求值函数
        def formula(args):
            # 有状态节点（使用 pre 或 fold）需要特殊处理
            if decl.is_stateful:
                # 获取前一时刻的状态
                prev_state = args.get('__state__')

                # 构建求值上下文，包含前一时刻的自身值
                eval_context = dict(args)
                if prev_state is not None:
                    eval_context[decl.name] = prev_state

                # 求值表达式
                new_value = self.evaluator.evaluate(expr, eval_context)

                # 返回 (value, new_state)
                return (new_value, new_value)

            # 普通表达式
            else:
                return self.evaluator.evaluate(expr, args)

        # 计算数据依赖（用于计算）
        # 规范化依赖：对于 stats.count 这样的依赖，如果 stats.count 不是源字段节点，
        # 则转换为 stats（基础流）
        dependencies = self._normalize_dependencies(decl.static_dependencies)

        # 如果有显式触发器，添加到依赖（用于计算时获取值）
        if decl.trigger:
            # 触发器也需要规范化
            normalized_trigger = self._normalize_dependency(decl.trigger)
            dependencies.add(normalized_trigger)

        # 移除自引用（pre 操作符处理的是历史值，不是当前值）
        dependencies.discard(decl.name)

        # 计算触发依赖（用于订阅）
        # 如果有显式触发器，只有触发器变化时才更新
        # 否则，所有依赖都是触发依赖
        trigger_deps = None
        if decl.trigger:
            trigger_deps = {normalized_trigger}

        self.engine.add_stream(
            decl.name,
            formula,
            dependencies,
            decl.is_stateful,
            None,
            trigger_deps
        )

    def _normalize_dependency(self, dep: str) -> str:
        """规范化单个依赖

        对于 stats.count 这样的依赖：
        - 如果 stats.count 是已知的源字段节点，返回 stats.count
        - 否则返回 stats（基础名称）
        """
        if '.' not in dep:
            return dep

        # 检查完整路径是否是源字段节点
        if dep in self.engine.nodes and self.engine.nodes[dep].is_source:
            return dep

        # 否则返回基础名称
        return dep.split('.')[0]

    def _normalize_dependencies(self, deps: List[str]) -> Set[str]:
        """规范化依赖列表"""
        return {self._normalize_dependency(dep) for dep in deps}

    def _compile_sink(self, decl: SinkDecl):
        """编译 Sink 声明"""
        expr = decl.expression
        raw_dependencies = extract_dependencies(expr)
        dependencies = self._normalize_dependencies(raw_dependencies)

        def formula(args):
            return self.evaluator.evaluate(expr, args)

        self.engine.add_sink(decl.name, formula, dependencies)

    def _extract_csv_info(self, expr) -> Optional[Dict]:
        """从表达式中提取 CSV 信息（如果是 load_csv 调用）"""
        if expr is None:
            return None

        if not isinstance(expr, FunctionCall):
            return None

        if expr.name != 'load_csv':
            return None

        # 提取参数
        if not expr.arguments or len(expr.arguments) < 1:
            return None

        # 第一个参数是文件路径
        path_arg = expr.arguments[0]
        if isinstance(path_arg, Literal) and path_arg.type_name == 'string':
            path = path_arg.value
        else:
            return None  # 路径必须是字符串字面量

        # 第二个参数是 skip_header（可选）
        skip_header = False
        if len(expr.arguments) > 1:
            skip_arg = expr.arguments[1]
            if isinstance(skip_arg, Literal) and skip_arg.type_name == 'bool':
                skip_header = skip_arg.value

        return {
            'path': path,
            'skip_header': skip_header
        }

    def _compute_ranks(self, stream_decls: List[StreamDecl]):
        """计算流声明的拓扑高度"""
        # 构建依赖图（移除自引用，包含触发器）
        deps_graph: Dict[str, set] = {}
        for decl in stream_decls:
            # 过滤掉自引用依赖（使用 pre 的情况）
            filtered_deps = {dep for dep in decl.static_dependencies if dep != decl.name}
            # 添加显式触发器
            if decl.trigger:
                filtered_deps.add(decl.trigger)
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

    def _initialize_values(self, statements: List):
        """初始化所有节点的值（触发初始传播）"""
        # 按拓扑顺序计算所有非源节点的初始值
        # 这样可以处理：
        # 1. 依赖源节点初始值的普通流
        # 2. 自引用的有状态节点（pre/fold）

        # 获取所有非源节点，按 rank 排序
        stream_nodes = [
            (name, node) for name, node in self.engine.nodes.items()
            if not node.is_source
        ]
        stream_nodes.sort(key=lambda x: x[1].rank)

        # 按拓扑顺序计算每个节点的初始值
        for name, node in stream_nodes:
            if node.formula:
                new_value = self.engine._recompute(node)
                node.cached_value = new_value

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
