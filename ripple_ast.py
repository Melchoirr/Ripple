"""
Ripple Language - AST 节点定义
抽象语法树节点类型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict, Tuple
from abc import ABC, abstractmethod


class ASTNode(ABC):
    """AST 节点基类"""

    @abstractmethod
    def __repr__(self):
        pass


# ================== 类型节点 ==================

@dataclass
class TypeNode(ASTNode):
    """类型节点基类"""
    pass


@dataclass
class BasicType(TypeNode):
    """基本类型：int, float, bool, string"""
    name: str  # 'int', 'float', 'bool', 'string'

    def __repr__(self):
        return f"BasicType({self.name})"


@dataclass
class StreamType(TypeNode):
    """流类型：Stream<T>"""
    element_type: TypeNode

    def __repr__(self):
        return f"Stream<{self.element_type}>"


@dataclass
class ArrayType(TypeNode):
    """数组类型：[T]"""
    element_type: TypeNode

    def __repr__(self):
        return f"[{self.element_type}]"


@dataclass
class FunctionType(TypeNode):
    """函数类型"""
    param_types: List[TypeNode]
    return_type: TypeNode

    def __repr__(self):
        params = ', '.join(str(t) for t in self.param_types)
        return f"({params}) -> {self.return_type}"


@dataclass
class StructType(TypeNode):
    """结构体类型：{ x: int, y: int }"""
    fields: Dict[str, TypeNode]  # 字段名 -> 字段类型

    def __repr__(self):
        fields_str = ', '.join(f"{k}: {v}" for k, v in self.fields.items())
        return f"{{ {fields_str} }}"


# ================== 表达式节点 ==================

@dataclass
class Expression(ASTNode):
    """表达式节点基类"""
    pass


@dataclass
class Literal(Expression):
    """字面量"""
    value: Any
    type_name: str  # 'int', 'float', 'bool', 'string'

    def __repr__(self):
        return f"Literal({self.value}:{self.type_name})"


@dataclass
class ArrayLiteral(Expression):
    """数组字面量：[1, 2, 3]"""
    elements: List[Expression]

    def __repr__(self):
        elems = ', '.join(str(e) for e in self.elements)
        return f"[{elems}]"


@dataclass
class ArrayAccess(Expression):
    """数组索引访问：arr[index]"""
    array: Expression
    index: Expression

    def __repr__(self):
        return f"{self.array}[{self.index}]"


@dataclass
class StructLiteral(Expression):
    """结构体字面量：{ x: 1, y: 2 }"""
    fields: Dict[str, Expression]  # 字段名 -> 字段值表达式

    def __repr__(self):
        fields_str = ', '.join(f"{k}: {v}" for k, v in self.fields.items())
        return f"{{ {fields_str} }}"


@dataclass
class FieldAccess(Expression):
    """字段访问：obj.field"""
    object: Expression
    field_name: str

    def __repr__(self):
        return f"{self.object}.{self.field_name}"


@dataclass
class Identifier(Expression):
    """标识符"""
    name: str

    def __repr__(self):
        return f"Identifier({self.name})"


@dataclass
class BinaryOp(Expression):
    """二元操作符"""
    operator: str  # '+', '-', '*', '/', '==', '<', etc.
    left: Expression
    right: Expression

    def __repr__(self):
        return f"BinaryOp({self.left} {self.operator} {self.right})"


@dataclass
class UnaryOp(Expression):
    """一元操作符"""
    operator: str  # '!', '-'
    operand: Expression

    def __repr__(self):
        return f"UnaryOp({self.operator}{self.operand})"


@dataclass
class FunctionCall(Expression):
    """函数调用"""
    name: str
    arguments: List[Expression]

    def __repr__(self):
        args = ', '.join(str(arg) for arg in self.arguments)
        return f"FunctionCall({self.name}({args}))"


@dataclass
class IfExpression(Expression):
    """条件表达式"""
    condition: Expression
    then_branch: Expression
    else_branch: Expression

    def __repr__(self):
        return f"If({self.condition}) Then({self.then_branch}) Else({self.else_branch})"


@dataclass
class Lambda(Expression):
    """Lambda 表达式"""
    parameters: List[str]
    body: Expression

    def __repr__(self):
        params = ', '.join(self.parameters)
        return f"Lambda(({params}) => {self.body})"


@dataclass
class LetExpression(Expression):
    """Let 表达式：let name = value in body"""
    name: str
    value: Expression
    body: Expression

    def __repr__(self):
        return f"let {self.name} = {self.value} in {self.body}"


# ================== 流操作符节点 ==================

@dataclass
class PreOp(Expression):
    """Pre 操作符：访问流的前一时刻值"""
    stream_name: str
    initial_value: Expression

    def __repr__(self):
        return f"pre({self.stream_name}, {self.initial_value})"


@dataclass
class FoldOp(Expression):
    """Fold 操作符：状态累积"""
    stream: Expression
    initial: Expression
    accumulator: Lambda  # (acc, x) => expression

    def __repr__(self):
        return f"fold({self.stream}, {self.initial}, {self.accumulator})"


# ================== 数组操作符节点 ==================

@dataclass
class MapOp(Expression):
    """Map 操作符：映射数组元素"""
    array: Expression
    mapper: Lambda  # (x) => expression

    def __repr__(self):
        return f"map({self.array}, {self.mapper})"


@dataclass
class FilterOp(Expression):
    """Filter 操作符：过滤数组元素"""
    array: Expression
    predicate: Lambda  # (x) => boolean

    def __repr__(self):
        return f"filter({self.array}, {self.predicate})"


@dataclass
class ReduceOp(Expression):
    """Reduce 操作符：归约数组"""
    array: Expression
    initial: Expression
    accumulator: Lambda  # (acc, x) => expression

    def __repr__(self):
        return f"reduce({self.array}, {self.initial}, {self.accumulator})"


# ================== 声明节点 ==================

@dataclass
class Statement(ASTNode):
    """语句节点基类"""
    pass


@dataclass
class SourceDecl(Statement):
    """源声明：source name : type := initial_value;"""
    name: str
    type_sig: TypeNode
    initial_value: Optional[Expression] = None

    # 用于图构建的元数据
    rank: int = 0  # 拓扑高度
    is_stateful: bool = False
    static_dependencies: List[str] = field(default_factory=list)

    def __repr__(self):
        init = f" := {self.initial_value}" if self.initial_value else ""
        return f"source {self.name} : {self.type_sig}{init};"


@dataclass
class StreamDecl(Statement):
    """流声明：stream name <- expression [on trigger];"""
    name: str
    expression: Expression
    trigger: Optional[str] = None  # 显式触发器

    # 用于图构建的元数据
    rank: int = 0  # 拓扑高度
    is_stateful: bool = False
    static_dependencies: List[str] = field(default_factory=list)

    def __repr__(self):
        if self.trigger:
            return f"stream {self.name} <- {self.expression} on {self.trigger};"
        return f"stream {self.name} <- {self.expression};"


@dataclass
class SinkDecl(Statement):
    """Sink 声明：sink name <- expression;"""
    name: str
    expression: Expression

    def __repr__(self):
        return f"sink {self.name} <- {self.expression};"


@dataclass
class FuncDecl(Statement):
    """函数声明：func name(params) = expression;"""
    name: str
    parameters: List[str]
    body: Expression

    def __repr__(self):
        params = ', '.join(self.parameters)
        return f"func {self.name}({params}) = {self.body};"


@dataclass
class TypeDecl(Statement):
    """类型定义：type Point = { x: int, y: int };"""
    name: str
    type_def: TypeNode  # 通常是 StructType

    def __repr__(self):
        return f"type {self.name} = {self.type_def};"


# ================== 程序节点 ==================

@dataclass
class Program(ASTNode):
    """程序：顶层声明列表"""
    statements: List[Statement]

    def __repr__(self):
        stmts = '\n'.join(str(s) for s in self.statements)
        return f"Program:\n{stmts}"


# ================== 工具函数 ==================

def extract_dependencies(expr: Expression, local_vars: set = None) -> List[str]:
    """从表达式中提取依赖的标识符列表"""
    if local_vars is None:
        local_vars = set()

    dependencies = []

    def visit(node, locals_set):
        if isinstance(node, Identifier):
            # 只有不在局部变量集合中的标识符才是外部依赖
            if node.name not in locals_set:
                dependencies.append(node.name)
        elif isinstance(node, BinaryOp):
            visit(node.left, locals_set)
            visit(node.right, locals_set)
        elif isinstance(node, UnaryOp):
            visit(node.operand, locals_set)
        elif isinstance(node, FunctionCall):
            for arg in node.arguments:
                visit(arg, locals_set)
        elif isinstance(node, IfExpression):
            visit(node.condition, locals_set)
            visit(node.then_branch, locals_set)
            visit(node.else_branch, locals_set)
        elif isinstance(node, LetExpression):
            # let name = value in body
            # value 使用当前作用域
            visit(node.value, locals_set)
            # body 使用扩展的作用域（包含 let 绑定的变量）
            let_locals = locals_set.copy()
            let_locals.add(node.name)
            visit(node.body, let_locals)
        elif isinstance(node, PreOp):
            # PreOp 引用的流名不受局部变量影响
            if node.stream_name not in locals_set:
                dependencies.append(node.stream_name)
        elif isinstance(node, FoldOp):
            # Fold 操作：stream 和 initial 使用当前作用域
            visit(node.stream, locals_set)
            visit(node.initial, locals_set)

            # Lambda body 使用扩展的作用域（包含 Lambda 参数）
            if isinstance(node.accumulator, Lambda):
                # 创建新的局部变量集合，包含 Lambda 参数
                lambda_locals = locals_set.copy()
                lambda_locals.update(node.accumulator.parameters)
                visit(node.accumulator.body, lambda_locals)

        # 数组相关节点
        elif isinstance(node, ArrayLiteral):
            for elem in node.elements:
                visit(elem, locals_set)
        elif isinstance(node, ArrayAccess):
            visit(node.array, locals_set)
            visit(node.index, locals_set)
        elif isinstance(node, MapOp):
            visit(node.array, locals_set)
            if isinstance(node.mapper, Lambda):
                lambda_locals = locals_set.copy()
                lambda_locals.update(node.mapper.parameters)
                visit(node.mapper.body, lambda_locals)
        elif isinstance(node, FilterOp):
            visit(node.array, locals_set)
            if isinstance(node.predicate, Lambda):
                lambda_locals = locals_set.copy()
                lambda_locals.update(node.predicate.parameters)
                visit(node.predicate.body, lambda_locals)
        elif isinstance(node, ReduceOp):
            visit(node.array, locals_set)
            visit(node.initial, locals_set)
            if isinstance(node.accumulator, Lambda):
                lambda_locals = locals_set.copy()
                lambda_locals.update(node.accumulator.parameters)
                visit(node.accumulator.body, lambda_locals)

        # 结构体相关节点
        elif isinstance(node, StructLiteral):
            for field_expr in node.fields.values():
                visit(field_expr, locals_set)
        elif isinstance(node, FieldAccess):
            # 字段访问：提取完整路径作为依赖
            # 例如 p.x -> 依赖 "p.x"
            field_path = _get_field_path(node)
            if field_path and field_path.split('.')[0] not in locals_set:
                dependencies.append(field_path)

    visit(expr, local_vars)
    return list(set(dependencies))  # 去重


def _get_field_path(expr: Expression) -> Optional[str]:
    """获取字段访问的完整路径，如 p.x 或 line.start.x"""
    if isinstance(expr, FieldAccess):
        base_path = _get_field_path(expr.object)
        if base_path:
            return f"{base_path}.{expr.field_name}"
        return None
    elif isinstance(expr, Identifier):
        return expr.name
    else:
        return None


def is_stateful_expr(expr: Expression) -> bool:
    """检查表达式是否包含状态操作（pre 或 fold）"""
    if isinstance(expr, PreOp) or isinstance(expr, FoldOp):
        return True
    elif isinstance(expr, BinaryOp):
        return is_stateful_expr(expr.left) or is_stateful_expr(expr.right)
    elif isinstance(expr, UnaryOp):
        return is_stateful_expr(expr.operand)
    elif isinstance(expr, FunctionCall):
        return any(is_stateful_expr(arg) for arg in expr.arguments)
    elif isinstance(expr, IfExpression):
        return (is_stateful_expr(expr.condition) or
                is_stateful_expr(expr.then_branch) or
                is_stateful_expr(expr.else_branch))
    elif isinstance(expr, LetExpression):
        return is_stateful_expr(expr.value) or is_stateful_expr(expr.body)
    # 数组相关节点
    elif isinstance(expr, ArrayLiteral):
        return any(is_stateful_expr(elem) for elem in expr.elements)
    elif isinstance(expr, ArrayAccess):
        return is_stateful_expr(expr.array) or is_stateful_expr(expr.index)
    elif isinstance(expr, MapOp):
        return is_stateful_expr(expr.array) or is_stateful_expr(expr.mapper.body)
    elif isinstance(expr, FilterOp):
        return is_stateful_expr(expr.array) or is_stateful_expr(expr.predicate.body)
    elif isinstance(expr, ReduceOp):
        return (is_stateful_expr(expr.array) or
                is_stateful_expr(expr.initial) or
                is_stateful_expr(expr.accumulator.body))
    # 结构体相关节点
    elif isinstance(expr, StructLiteral):
        return any(is_stateful_expr(v) for v in expr.fields.values())
    elif isinstance(expr, FieldAccess):
        return is_stateful_expr(expr.object)
    return False
