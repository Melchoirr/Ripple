"""
Ripple Language - Graph Engine (图归约引擎)
实现基于依赖图的响应式运行时
"""

from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import heapq
import csv
import os
from ripple_ast import *


def _infer_csv_value(s: str) -> Any:
    """推断 CSV 单元格的值类型"""
    s = s.strip()
    if not s:
        return None

    # 尝试整数
    try:
        return int(s)
    except ValueError:
        pass

    # 尝试浮点数
    try:
        return float(s)
    except ValueError:
        pass

    # 尝试布尔值
    if s.lower() in ('true', 'false'):
        return s.lower() == 'true'

    # 默认字符串
    return s


def _load_csv_file(path: str, skip_header: bool = False) -> List[List[Any]]:
    """
    加载 CSV 文件，自动推断类型

    Args:
        path: CSV 文件路径
        skip_header: 是否跳过第一行（表头）

    Returns:
        2D 列表，每个元素自动推断类型
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if skip_header and i == 0:
                continue
            parsed_row = [_infer_csv_value(cell) for cell in row]
            rows.append(parsed_row)

    return rows


def _get_csv_header(path: str) -> List[str]:
    """获取 CSV 文件的表头（第一行）"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        return next(reader, [])


def _get_csv_column(data: List[List[Any]], col: int) -> List[Any]:
    """获取 CSV 数据的某一列"""
    return [row[col] if col < len(row) else None for row in data]


def _get_csv_row(data: List[List[Any]], row_idx: int) -> List[Any]:
    """获取 CSV 数据的某一行"""
    if 0 <= row_idx < len(data):
        return data[row_idx]
    return []


@dataclass
class GraphNode:
    """图中的节点"""
    name: str
    formula: Optional[Callable] = None  # 计算公式
    cached_value: Any = None  # 缓存的值
    rank: int = 0  # 拓扑高度
    is_stateful: bool = False  # 是否有状态
    state: Any = None  # 状态存储（用于 pre 和 fold）
    dependencies: Set[str] = field(default_factory=set)  # 依赖的节点
    subscribers: Set[str] = field(default_factory=set)  # 订阅者（子节点）
    is_dirty: bool = False  # 是否需要重新计算
    is_source: bool = False  # 是否是源节点
    has_trigger: bool = False  # 是否有触发器（on trigger）
    initial_value: Any = None  # 初始值（用于 on trigger 的流）


@dataclass
class PriorityQueueItem:
    """优先队列项"""
    rank: int
    name: str

    def __lt__(self, other):
        return self.rank < other.rank


class RippleEngine:
    """Ripple 图归约引擎"""

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.priority_queue: List[PriorityQueueItem] = []
        self.in_queue: Set[str] = set()
        self.time_step = 0
        self.sinks: List[str] = []  # Sink 节点列表
        self.context: Dict[str, Any] = {}  # Lambda 表达式的上下文

    def add_source(self, name: str, initial_value: Any = None):
        """添加源节点"""
        node = GraphNode(
            name=name,
            cached_value=initial_value,
            rank=0,
            is_source=True
        )
        self.nodes[name] = node

    def add_stream(self, name: str, formula: Callable, dependencies: Set[str],
                   is_stateful: bool = False, initial_state: Any = None,
                   trigger_deps: Set[str] = None, initial_value: Any = 0):
        """添加流节点

        Args:
            trigger_deps: 触发依赖（只有这些依赖变化时才重新计算）
                          如果为 None，则所有 dependencies 都是触发依赖
            initial_value: 初始值（用于有触发器的流）
        """
        # 计算 rank（基于依赖节点的最大 rank + 1）
        max_dep_rank = 0
        for dep in dependencies:
            if dep in self.nodes:
                max_dep_rank = max(max_dep_rank, self.nodes[dep].rank)

        rank = max_dep_rank + 1
        has_trigger = trigger_deps is not None

        node = GraphNode(
            name=name,
            formula=formula,
            rank=rank,
            is_stateful=is_stateful,
            state=initial_state,
            dependencies=dependencies,
            has_trigger=has_trigger,
            initial_value=initial_value
        )
        self.nodes[name] = node

        # 确定哪些依赖应该触发更新
        subscribe_deps = trigger_deps if trigger_deps is not None else dependencies

        # 只注册到触发依赖的订阅者列表
        for dep in subscribe_deps:
            if dep in self.nodes:
                self.nodes[dep].subscribers.add(name)

    def add_sink(self, name: str, formula: Callable, dependencies: Set[str]):
        """添加 Sink 节点（输出节点）"""
        self.add_stream(name, formula, dependencies)
        self.sinks.append(name)

    def push_event(self, source_name: str, value: Any):
        """向源节点推送事件"""
        # 检查是否是结构体整体更新
        if source_name in self.nodes and not self.nodes[source_name].is_source:
            # 可能是结构体虚拟节点，尝试更新字段节点
            if isinstance(value, dict):
                updated_any = False
                for field_name, field_value in value.items():
                    field_node_name = f"{source_name}.{field_name}"
                    if field_node_name in self.nodes and self.nodes[field_node_name].is_source:
                        self._update_source(field_node_name, field_value)
                        updated_any = True
                if updated_any:
                    self.propagate()
                    return
            raise ValueError(f"'{source_name}' is not a source node")

        if source_name not in self.nodes:
            raise ValueError(f"Source '{source_name}' not found")

        node = self.nodes[source_name]
        if not node.is_source:
            raise ValueError(f"'{source_name}' is not a source node")

        self._update_source(source_name, value)
        self.propagate()

    def _update_source(self, source_name: str, value: Any):
        """更新单个源节点的值"""
        node = self.nodes[source_name]
        node.cached_value = value
        node.is_dirty = True

        # 将所有订阅者加入优先队列
        for subscriber in node.subscribers:
            self._enqueue(subscriber)

    def _enqueue(self, name: str):
        """将节点加入优先队列"""
        if name not in self.in_queue:
            node = self.nodes[name]
            heapq.heappush(self.priority_queue, PriorityQueueItem(node.rank, name))
            self.in_queue.add(name)

    def propagate(self):
        """执行变化传播（基于高度的拓扑排序）"""
        while self.priority_queue:
            # 从优先队列中取出 rank 最小的节点
            item = heapq.heappop(self.priority_queue)
            node_name = item.name
            self.in_queue.remove(node_name)

            node = self.nodes[node_name]

            # 重新计算节点的值
            new_value = self._recompute(node)

            # 如果值发生变化，通知订阅者
            if new_value != node.cached_value:
                node.cached_value = new_value

                # 将所有订阅者加入优先队列
                for subscriber in node.subscribers:
                    self._enqueue(subscriber)

        self.time_step += 1

    def _recompute(self, node: GraphNode) -> Any:
        """重新计算节点的值"""
        if node.is_source:
            return node.cached_value

        if node.formula is None:
            return None

        # 构建参数字典
        args = {}
        for dep in node.dependencies:
            if dep in self.nodes:
                args[dep] = self.nodes[dep].cached_value

        # 如果是有状态节点，传递状态
        if node.is_stateful:
            args['__state__'] = node.state

        # 设置上下文
        self.context = args

        # 执行计算
        try:
            result = node.formula(args)

            # 如果返回了新状态，更新状态
            if isinstance(result, tuple) and len(result) == 2:
                value, new_state = result
                node.state = new_state
                return value
            else:
                return result
        except Exception as e:
            print(f"Error computing node '{node.name}': {e}")
            return None

    def get_value(self, name: str) -> Any:
        """获取节点的当前值"""
        if name not in self.nodes:
            return None
        return self.nodes[name].cached_value

    def get_sink_outputs(self) -> Dict[str, Any]:
        """获取所有 Sink 节点的输出"""
        return {sink: self.get_value(sink) for sink in self.sinks}

    def print_graph(self):
        """打印依赖图结构"""
        print("\n依赖图结构：")
        print("=" * 80)
        for name, node in sorted(self.nodes.items(), key=lambda x: x[1].rank):
            node_type = "SOURCE" if node.is_source else "STREAM"
            stateful = " [STATEFUL]" if node.is_stateful else ""
            print(f"[Rank {node.rank}] {node_type} {name}{stateful}")
            print(f"  Value: {node.cached_value}")
            if node.dependencies:
                print(f"  Dependencies: {', '.join(node.dependencies)}")
            if node.subscribers:
                print(f"  Subscribers: {', '.join(node.subscribers)}")
            print()


class ExpressionEvaluator:
    """表达式求值器"""

    def __init__(self, engine: RippleEngine):
        self.engine = engine
        self.user_functions: Dict[str, Any] = {}  # 用户定义的函数

    def evaluate(self, expr: Expression, context: Dict[str, Any]) -> Any:
        """求值表达式"""
        if isinstance(expr, Literal):
            return expr.value

        elif isinstance(expr, Identifier):
            if expr.name in context:
                return context[expr.name]
            else:
                raise ValueError(f"Identifier '{expr.name}' not found in context")

        elif isinstance(expr, BinaryOp):
            left = self.evaluate(expr.left, context)
            right = self.evaluate(expr.right, context)
            return self._apply_binary_op(expr.operator, left, right)

        elif isinstance(expr, UnaryOp):
            operand = self.evaluate(expr.operand, context)
            return self._apply_unary_op(expr.operator, operand)

        elif isinstance(expr, IfExpression):
            condition = self.evaluate(expr.condition, context)
            if condition:
                return self.evaluate(expr.then_branch, context)
            else:
                return self.evaluate(expr.else_branch, context)

        elif isinstance(expr, PreOp):
            # Pre 操作符：返回前一时刻的值
            stream_name = expr.stream_name
            state = context.get('__temporal_state__', {})
            pre_key = f'__pre_{stream_name}__'
            current_node = context.get('__current_node__')

            # 检查是否是自引用（pre(counter, 0) 在 counter 流中）
            is_self_ref = (stream_name == current_node)

            # 获取前一个值（或初始值）
            if pre_key in state:
                prev_value = state[pre_key]
            else:
                prev_value = self.evaluate(expr.initial_value, context)

            if is_self_ref:
                # 自引用：标记需要在计算完成后更新状态
                # 状态更新将在外层处理（返回值会成为下次的 prev）
                state['__self_ref_pre__'] = True
            else:
                # 非自引用：获取当前值并存储
                current_value = context.get(stream_name)
                if current_value is None and stream_name in self.engine.nodes:
                    current_value = self.engine.nodes[stream_name].cached_value
                state[pre_key] = current_value

            context['__temporal_state__'] = state
            return prev_value

        elif isinstance(expr, FoldOp):
            # Fold 操作符：时间上的状态累积
            # fold(stream, initial, (acc, v) => body)
            # 每次 stream 变化时，用累积函数更新状态
            state = context.get('__temporal_state__', {})
            fold_key = '__fold_acc__'
            init_key = '__fold_initialized__'

            # 首次初始化时，返回初始值，不应用累积函数
            if init_key not in state:
                initial = self.evaluate(expr.initial, context)
                state[fold_key] = initial
                state[init_key] = True
                context['__temporal_state__'] = state
                return initial

            # 获取当前累积值
            acc = state[fold_key]

            # 获取当前输入值
            current_value = self.evaluate(expr.stream, context)
            accumulator_func = expr.accumulator

            # 对当前值应用累积函数（单次应用）
            lambda_context = dict(context)
            lambda_context[accumulator_func.parameters[0]] = acc
            lambda_context[accumulator_func.parameters[1]] = current_value
            new_acc = self.evaluate(accumulator_func.body, lambda_context)

            # 更新状态
            state[fold_key] = new_acc
            context['__temporal_state__'] = state

            return new_acc

        elif isinstance(expr, FunctionCall):
            # 先检查用户定义的函数
            if expr.name in self.user_functions:
                return self._apply_user_function(expr.name, expr.arguments, context)

            # 特殊处理 count_if（带 Lambda 参数）
            if expr.name == 'count_if' and len(expr.arguments) == 2:
                array = self.evaluate(expr.arguments[0], context)
                predicate = expr.arguments[1]
                if isinstance(predicate, Lambda):
                    count = 0
                    for elem in array:
                        lambda_context = dict(context)
                        lambda_context[predicate.parameters[0]] = elem
                        if self.evaluate(predicate.body, lambda_context):
                            count += 1
                    return count

            # 否则使用内置函数
            args = [self.evaluate(arg, context) for arg in expr.arguments]
            return self._apply_function(expr.name, args)

        elif isinstance(expr, LetExpression):
            # let name = value in body
            # 先求值 value
            value = self.evaluate(expr.value, context)
            # 创建扩展的上下文，包含新绑定
            let_context = dict(context)
            let_context[expr.name] = value
            # 在扩展上下文中求值 body
            return self.evaluate(expr.body, let_context)

        # 数组相关表达式
        elif isinstance(expr, ArrayLiteral):
            return [self.evaluate(elem, context) for elem in expr.elements]

        elif isinstance(expr, ArrayAccess):
            array = self.evaluate(expr.array, context)
            index = self.evaluate(expr.index, context)

            if not isinstance(array, list):
                raise ValueError(f"Cannot index non-array type: {type(array)}")
            if not isinstance(index, int):
                raise ValueError(f"Array index must be int, got: {type(index)}")
            if index < 0 or index >= len(array):
                raise IndexError(f"Array index {index} out of bounds (length={len(array)})")

            return array[index]

        elif isinstance(expr, MapOp):
            array = self.evaluate(expr.array, context)

            if not isinstance(array, list):
                raise ValueError(f"map expects array, got: {type(array)}")

            result = []
            for elem in array:
                elem_context = dict(context)
                elem_context[expr.mapper.parameters[0]] = elem
                mapped_value = self.evaluate(expr.mapper.body, elem_context)
                result.append(mapped_value)

            return result

        elif isinstance(expr, FilterOp):
            array = self.evaluate(expr.array, context)

            if not isinstance(array, list):
                raise ValueError(f"filter expects array, got: {type(array)}")

            result = []
            for elem in array:
                elem_context = dict(context)
                elem_context[expr.predicate.parameters[0]] = elem
                should_include = self.evaluate(expr.predicate.body, elem_context)
                if should_include:
                    result.append(elem)

            return result

        elif isinstance(expr, ReduceOp):
            array = self.evaluate(expr.array, context)

            if not isinstance(array, list):
                raise ValueError(f"reduce expects array, got: {type(array)}")

            acc = self.evaluate(expr.initial, context)

            for elem in array:
                # 继承外部上下文，以便访问外部变量
                lambda_context = dict(context)
                lambda_context[expr.accumulator.parameters[0]] = acc
                lambda_context[expr.accumulator.parameters[1]] = elem
                acc = self.evaluate(expr.accumulator.body, lambda_context)

            return acc

        # 结构体相关表达式
        elif isinstance(expr, StructLiteral):
            return {
                field_name: self.evaluate(field_expr, context)
                for field_name, field_expr in expr.fields.items()
            }

        elif isinstance(expr, FieldAccess):
            # 尝试直接查找完整字段路径（用于字段级依赖）
            field_path = self._get_field_path(expr)
            if field_path and field_path in context:
                return context[field_path]

            # 否则求值 object 并访问字段
            obj = self.evaluate(expr.object, context)
            if not isinstance(obj, dict):
                raise ValueError(f"Cannot access field on non-struct type: {type(obj)}")
            if expr.field_name not in obj:
                raise ValueError(f"Struct has no field '{expr.field_name}'")
            return obj[expr.field_name]

        else:
            raise ValueError(f"Unsupported expression type: {type(expr)}")

    def _apply_binary_op(self, op: str, left: Any, right: Any) -> Any:
        """应用二元操作符"""
        operators = {
            '+': lambda l, r: l + r,
            '-': lambda l, r: l - r,
            '*': lambda l, r: l * r,
            '/': lambda l, r: l / r if r != 0 else float('inf'),
            '%': lambda l, r: l % r,
            '==': lambda l, r: l == r,
            '!=': lambda l, r: l != r,
            '<': lambda l, r: l < r,
            '>': lambda l, r: l > r,
            '<=': lambda l, r: l <= r,
            '>=': lambda l, r: l >= r,
            '&&': lambda l, r: l and r,
            '||': lambda l, r: l or r,
        }

        if op in operators:
            return operators[op](left, right)
        else:
            raise ValueError(f"Unknown binary operator: {op}")

    def _get_field_path(self, expr: Expression) -> Optional[str]:
        """获取字段访问的完整路径，如 p.x 或 line.start.x"""
        if isinstance(expr, FieldAccess):
            base_path = self._get_field_path(expr.object)
            if base_path:
                return f"{base_path}.{expr.field_name}"
            return None
        elif isinstance(expr, Identifier):
            return expr.name
        else:
            return None

    def _apply_unary_op(self, op: str, operand: Any) -> Any:
        """应用一元操作符"""
        if op == '!':
            return not operand
        elif op == '-':
            return -operand
        else:
            raise ValueError(f"Unknown unary operator: {op}")

    def _apply_function(self, name: str, args: List[Any]) -> Any:
        """应用内置函数"""
        builtin_functions = {
            # 数学函数
            'abs': lambda x: abs(x),
            'max': lambda *args: max(args) if len(args) > 1 else max(args[0]) if isinstance(args[0], list) else args[0],
            'min': lambda *args: min(args) if len(args) > 1 else min(args[0]) if isinstance(args[0], list) else args[0],
            'sqrt': lambda x: x ** 0.5,

            # 数组函数
            'len': lambda arr: len(arr) if isinstance(arr, list) else len(str(arr)),
            'head': lambda arr: arr[0] if arr else None,
            'tail': lambda arr: arr[1:] if isinstance(arr, list) else [],
            'last': lambda arr: arr[-1] if arr else None,
            'sum': lambda arr: sum(arr) if isinstance(arr, list) else arr,
            'reverse': lambda arr: list(reversed(arr)) if isinstance(arr, list) else arr,

            # 矩阵函数
            'transpose': lambda m: [[row[i] for row in m] for i in range(len(m[0]))] if m and m[0] else [],

            # CSV 文件函数
            'load_csv': lambda path, *args: _load_csv_file(path, args[0] if args else False),
            'csv_header': lambda path: _get_csv_header(path),
            'col': lambda data, i: _get_csv_column(data, i),
            'row': lambda data, i: _get_csv_row(data, i),

            # 统计函数
            'avg': lambda arr: sum(arr) / len(arr) if arr else 0,
            'count': lambda arr: len(arr),
            'count_if': lambda arr, pred: sum(1 for x in arr if pred(x)),
        }

        if name in builtin_functions:
            return builtin_functions[name](*args)
        else:
            raise ValueError(f"Unknown function: {name}")

    def _apply_user_function(self, name: str, arg_exprs: List, context: Dict[str, Any]) -> Any:
        """应用用户定义的函数"""
        func_decl = self.user_functions[name]

        # 检查参数数量
        if len(arg_exprs) != len(func_decl.parameters):
            raise ValueError(
                f"Function '{name}' expects {len(func_decl.parameters)} arguments, "
                f"got {len(arg_exprs)}"
            )

        # 求值参数
        arg_values = [self.evaluate(arg, context) for arg in arg_exprs]

        # 创建函数的局部上下文
        func_context = dict(context)
        for param, value in zip(func_decl.parameters, arg_values):
            func_context[param] = value

        # 求值函数体
        return self.evaluate(func_decl.body, func_context)


# 测试代码
if __name__ == "__main__":
    # 创建引擎
    engine = RippleEngine()

    # 添加源节点
    engine.add_source("A", 1)

    # 添加流节点
    engine.add_stream(
        "B",
        lambda args: args["A"] * 2,
        {"A"}
    )

    engine.add_stream(
        "C",
        lambda args: args["A"] + 1,
        {"A"}
    )

    engine.add_stream(
        "D",
        lambda args: args["B"] + args["C"],
        {"B", "C"}
    )

    # 打印初始图结构
    engine.print_graph()

    # 推送事件
    print("\n推送事件: A = 2")
    engine.push_event("A", 2)

    print("\n传播后的值：")
    print(f"A = {engine.get_value('A')}")
    print(f"B = {engine.get_value('B')}")
    print(f"C = {engine.get_value('C')}")
    print(f"D = {engine.get_value('D')}")

    print("\n推送事件: A = 5")
    engine.push_event("A", 5)

    print("\n传播后的值：")
    print(f"A = {engine.get_value('A')}")
    print(f"B = {engine.get_value('B')}")
    print(f"C = {engine.get_value('C')}")
    print(f"D = {engine.get_value('D')}")
