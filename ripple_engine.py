"""
Ripple Language - Graph Engine (图归约引擎)
实现基于依赖图的响应式运行时
"""

from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import heapq
from ripple_ast import *


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
                   is_stateful: bool = False, initial_state: Any = None):
        """添加流节点"""
        # 计算 rank（基于依赖节点的最大 rank + 1）
        max_dep_rank = 0
        for dep in dependencies:
            if dep in self.nodes:
                max_dep_rank = max(max_dep_rank, self.nodes[dep].rank)

        rank = max_dep_rank + 1

        node = GraphNode(
            name=name,
            formula=formula,
            rank=rank,
            is_stateful=is_stateful,
            state=initial_state,
            dependencies=dependencies
        )
        self.nodes[name] = node

        # 注册到依赖节点的订阅者列表
        for dep in dependencies:
            if dep in self.nodes:
                self.nodes[dep].subscribers.add(name)

    def add_sink(self, name: str, formula: Callable, dependencies: Set[str]):
        """添加 Sink 节点（输出节点）"""
        self.add_stream(name, formula, dependencies)
        self.sinks.append(name)

    def push_event(self, source_name: str, value: Any):
        """向源节点推送事件"""
        if source_name not in self.nodes:
            raise ValueError(f"Source '{source_name}' not found")

        node = self.nodes[source_name]
        if not node.is_source:
            raise ValueError(f"'{source_name}' is not a source node")

        # 更新源节点的值
        node.cached_value = value
        node.is_dirty = True

        # 将所有订阅者加入优先队列
        for subscriber in node.subscribers:
            self._enqueue(subscriber)

        # 触发传播
        self.propagate()

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
            if stream_name in self.engine.nodes:
                node = self.engine.nodes[stream_name]
                if node.state is not None:
                    return node.state
                else:
                    return self.evaluate(expr.initial_value, context)
            else:
                return self.evaluate(expr.initial_value, context)

        elif isinstance(expr, FoldOp):
            # Fold 操作符：累积状态
            stream_value = self.evaluate(expr.stream, context)
            accumulator_func = expr.accumulator

            # 获取当前状态
            if '__state__' in context and context['__state__'] is not None:
                acc = context['__state__']
            else:
                acc = self.evaluate(expr.initial, context)

            # 应用累积函数
            lambda_context = {
                accumulator_func.parameters[0]: acc,
                accumulator_func.parameters[1]: stream_value
            }
            new_acc = self.evaluate(accumulator_func.body, lambda_context)

            return new_acc

        elif isinstance(expr, FunctionCall):
            # 简单的内置函数
            args = [self.evaluate(arg, context) for arg in expr.arguments]
            return self._apply_function(expr.name, args)

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
            'abs': lambda x: abs(x),
            'max': lambda *args: max(args),
            'min': lambda *args: min(args),
            'sqrt': lambda x: x ** 0.5,
        }

        if name in builtin_functions:
            return builtin_functions[name](*args)
        else:
            raise ValueError(f"Unknown function: {name}")


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
