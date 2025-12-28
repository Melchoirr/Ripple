"""
Ripple Language - Enhanced Compiler (增强版编译器)
集成完整的错误处理机制
"""

from typing import Dict, Any, Callable, Set, List, Optional
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

    def __init__(self, verbose: bool = False):
        self.engine = RippleEngine()
        self.evaluator = ExpressionEvaluator(self.engine)
        self.source_code = ""
        self.error_reporter = None
        self.user_functions: Dict[str, FuncDecl] = {}
        self.type_defs: Dict[str, TypeNode] = {}
        self.type_checker = TypeChecker()
        self.csv_sources: Dict[str, Dict] = {}
        self.verbose = verbose

    def _log(self, msg: str):
        """仅在 verbose 模式下打印"""
        if self.verbose:
            print(msg)

    def compile(self, ast: Program):
        """编译程序（带错误检查）"""
        self.error_reporter = ErrorReporter(self.source_code)

        # 0a. 编译类型定义
        for stmt in ast.statements:
            if isinstance(stmt, TypeDecl):
                self._compile_type_decl(stmt)

        # 0b. 编译函数定义
        for stmt in ast.statements:
            if isinstance(stmt, FuncDecl):
                self._compile_func(stmt)

        self.evaluator.user_functions = self.user_functions

        # 0c. 类型推断与检查
        self.type_checker.type_aliases = self.type_defs
        self.type_checker.user_functions = self.user_functions
        self.type_checker.check_program(ast)

        # 1. 检查重复定义
        duplicate_errors = DuplicateDefinitionChecker.check(ast.statements)
        for error in duplicate_errors:
            self.error_reporter.add_error(error)

        if self.error_reporter.has_errors():
            self.error_reporter.print_report()
            self.error_reporter.raise_if_errors()

        # 2. 收集所有定义
        source_names = set()
        stream_decls = []

        for stmt in ast.statements:
            if isinstance(stmt, SourceDecl):
                source_names.add(stmt.name)
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
        undefined_errors = UndefinedReferenceChecker.check(stream_decls, source_names)
        for error in undefined_errors:
            self.error_reporter.add_error(error)

        if self.error_reporter.has_errors():
            self.error_reporter.print_report()
            self.error_reporter.raise_if_errors()

        # 4. 检查循环依赖
        cycle_errors = self._detect_circular_dependencies(stream_decls)
        for error in cycle_errors:
            self.error_reporter.add_error(error)

        if self.error_reporter.has_errors():
            self.error_reporter.print_report()
            self.error_reporter.raise_if_errors()

        # 5. 编译源声明
        for stmt in ast.statements:
            if isinstance(stmt, SourceDecl):
                self._compile_source(stmt)

        # 6. 计算 rank 并编译流声明
        self._compute_ranks(stream_decls)

        for stmt in sorted(stream_decls, key=lambda s: s.rank):
            self._compile_stream(stmt)

        # 7. 编译 Sink 声明
        for stmt in ast.statements:
            if isinstance(stmt, SinkDecl):
                self._compile_sink(stmt)

        # 8. 初始化所有节点值
        self._initialize_values(ast.statements)

    def _detect_circular_dependencies(self, stream_decls: List[StreamDecl]) -> List[CircularDependencyError]:
        """检测循环依赖"""
        errors = []
        deps_graph: Dict[str, Set[str]] = {}
        for decl in stream_decls:
            filtered_deps = {dep for dep in decl.static_dependencies if dep != decl.name}
            if decl.trigger:
                filtered_deps.add(decl.trigger)
            deps_graph[decl.name] = filtered_deps

        detector = CircularDependencyDetector()
        cycles = detector.find_all_cycles(deps_graph)

        for cycle in cycles:
            errors.append(CircularDependencyError(cycle))

        return errors

    def _compile_source(self, decl: SourceDecl):
        """编译源声明"""
        initial_value = None

        csv_info = self._extract_csv_info(decl.initial_value)
        if csv_info:
            self.csv_sources[decl.name] = csv_info

        if decl.initial_value:
            try:
                initial_value = self.evaluator.evaluate(decl.initial_value, {})
            except Exception as e:
                raise CompileError(f"Error evaluating initial value for source '{decl.name}': {e}")

        type_sig = decl.type_sig
        if type_sig is None:
            inferred_type = self.type_checker.get_type(decl.name)
            if inferred_type:
                type_sig = inferred_type

        struct_type = self._get_struct_type(type_sig)

        if struct_type:
            self._compile_struct_source(decl.name, struct_type, initial_value)
        else:
            self.engine.add_source(decl.name, initial_value)

    def _type_to_string(self, type_node: TypeNode) -> str:
        """将类型节点转换为可读字符串"""
        if type_node is None:
            return "unknown"
        if isinstance(type_node, BasicType):
            return type_node.name
        elif isinstance(type_node, ArrayType):
            return f"[{self._type_to_string(type_node.element_type)}]"
        elif isinstance(type_node, StructType):
            fields_str = ", ".join(f"{k}: {self._type_to_string(v)}" for k, v in type_node.fields.items())
            return f"{{{fields_str}}}"
        elif isinstance(type_node, FunctionType):
            params_str = ", ".join(self._type_to_string(p) for p in type_node.param_types)
            return f"({params_str}) -> {self._type_to_string(type_node.return_type)}"
        else:
            return str(type_node)

    def _get_struct_type(self, type_sig: Optional[TypeNode]) -> Optional[StructType]:
        """获取结构体类型"""
        if type_sig is None:
            return None
        if isinstance(type_sig, StructType):
            return type_sig
        elif isinstance(type_sig, BasicType):
            if type_sig.name in self.type_defs:
                type_def = self.type_defs[type_sig.name]
                if isinstance(type_def, StructType):
                    return type_def
        return None

    def _compile_struct_source(self, name: str, struct_type: StructType, initial_value: Any):
        """编译结构体源"""
        field_names = list(struct_type.fields.keys())

        for field_name in field_names:
            field_node_name = f"{name}.{field_name}"
            field_initial = None
            if initial_value and isinstance(initial_value, dict):
                field_initial = initial_value.get(field_name)
            self.engine.add_source(field_node_name, field_initial)

        field_deps = {f"{name}.{f}" for f in field_names}

        def struct_formula(args):
            return {field_name: args.get(f"{name}.{field_name}") for field_name in field_names}

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

        def formula(args):
            eval_context = dict(args)
            # 传递当前节点名称（用于处理自引用 pre）
            eval_context['__current_node__'] = decl.name

            if decl.is_stateful:
                prev_state = args.get('__state__')
                if prev_state is None:
                    prev_state = {}
                # 传递状态信息给 evaluator
                eval_context['__temporal_state__'] = prev_state
                new_value = self.evaluator.evaluate(expr, eval_context)
                # 获取更新后的状态
                new_state = eval_context.get('__temporal_state__', prev_state)
                # 处理自引用 pre：将计算结果存储为下次的"前一个值"
                if new_state.get('__self_ref_pre__'):
                    pre_key = f'__pre_{decl.name}__'
                    new_state[pre_key] = new_value
                    del new_state['__self_ref_pre__']
                return (new_value, new_state)
            else:
                return self.evaluator.evaluate(expr, eval_context)

        dependencies = self._normalize_dependencies(decl.static_dependencies)

        if decl.trigger:
            normalized_trigger = self._normalize_dependency(decl.trigger)
            dependencies.add(normalized_trigger)

        dependencies.discard(decl.name)

        trigger_deps = None
        if decl.trigger:
            trigger_deps = {normalized_trigger}

        self.engine.add_stream(decl.name, formula, dependencies, decl.is_stateful, None, trigger_deps)

    def _normalize_dependency(self, dep: str) -> str:
        """规范化单个依赖"""
        if '.' not in dep:
            return dep
        if dep in self.engine.nodes and self.engine.nodes[dep].is_source:
            return dep
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
        """从表达式中提取 CSV 信息"""
        if expr is None:
            return None
        if not isinstance(expr, FunctionCall):
            return None
        if expr.name != 'load_csv':
            return None
        if not expr.arguments or len(expr.arguments) < 1:
            return None

        path_arg = expr.arguments[0]
        if isinstance(path_arg, Literal) and path_arg.type_name == 'string':
            path = path_arg.value
        else:
            return None

        skip_header = False
        if len(expr.arguments) > 1:
            skip_arg = expr.arguments[1]
            if isinstance(skip_arg, Literal) and skip_arg.type_name == 'bool':
                skip_header = skip_arg.value

        return {'path': path, 'skip_header': skip_header}

    def _compute_ranks(self, stream_decls: List[StreamDecl]):
        """计算流声明的拓扑高度"""
        deps_graph: Dict[str, set] = {}
        for decl in stream_decls:
            filtered_deps = {dep for dep in decl.static_dependencies if dep != decl.name}
            if decl.trigger:
                filtered_deps.add(decl.trigger)
            deps_graph[decl.name] = filtered_deps

        ranks: Dict[str, int] = {}
        visited: set = set()

        def compute_rank(name: str) -> int:
            if name in ranks:
                return ranks[name]
            if name in visited:
                raise CircularDependencyError([name])
            visited.add(name)

            if name not in deps_graph or not deps_graph[name]:
                ranks[name] = 0
                visited.remove(name)
                return 0

            max_dep_rank = 0
            for dep in deps_graph[name]:
                if dep in deps_graph:
                    dep_rank = compute_rank(dep)
                    max_dep_rank = max(max_dep_rank, dep_rank)

            rank = max_dep_rank + 1
            ranks[name] = rank
            visited.remove(name)
            return rank

        for decl in stream_decls:
            decl.rank = compute_rank(decl.name)

    def _initialize_values(self, statements: List):
        """初始化所有节点的值"""
        stream_nodes = [(name, node) for name, node in self.engine.nodes.items() if not node.is_source]
        stream_nodes.sort(key=lambda x: x[1].rank)

        for name, node in stream_nodes:
            if node.formula:
                # 有触发器的流不在初始化时执行公式，使用初始值
                if node.has_trigger:
                    node.cached_value = node.initial_value
                else:
                    new_value = self.engine._recompute(node)
                    node.cached_value = new_value

    def run(self, source_code: str) -> RippleEngine:
        """编译并返回引擎"""
        self.source_code = source_code

        try:
            lexer = RippleLexer(source_code)
            tokens = lexer.tokenize()

            parser = RippleParser(tokens)
            ast = parser.parse()

            self.compile(ast)

            return self.engine

        except CompileError as e:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise


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

    compiler1 = RippleCompiler(verbose=True)
    try:
        engine1 = compiler1.run(code1)
        print("\n推送事件: A = 2")
        engine1.push_event("A", 2)
        print(f"输出: {engine1.get_sink_outputs()}")
    except Exception as e:
        print(f"错误: {e}")
