"""
Ripple Language - AST 节点定义
抽象语法树节点类型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
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
class FunctionType(TypeNode):
    """函数类型"""
    param_types: List[TypeNode]
    return_type: TypeNode

    def __repr__(self):
        params = ', '.join(str(t) for t in self.param_types)
        return f"({params}) -> {self.return_type}"


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
    """流声明：stream name <- expression;"""
    name: str
    expression: Expression

    # 用于图构建的元数据
    rank: int = 0  # 拓扑高度
    is_stateful: bool = False
    static_dependencies: List[str] = field(default_factory=list)

    def __repr__(self):
        return f"stream {self.name} <- {self.expression};"


@dataclass
class SinkDecl(Statement):
    """Sink 声明：sink name <- expression;"""
    name: str
    expression: Expression

    def __repr__(self):
        return f"sink {self.name} <- {self.expression};"


# ================== 程序节点 ==================

@dataclass
class Program(ASTNode):
    """程序：顶层声明列表"""
    statements: List[Statement]

    def __repr__(self):
        stmts = '\n'.join(str(s) for s in self.statements)
        return f"Program:\n{stmts}"


# ================== 工具函数 ==================

def extract_dependencies(expr: Expression) -> List[str]:
    """从表达式中提取依赖的标识符列表"""
    dependencies = []

    def visit(node):
        if isinstance(node, Identifier):
            dependencies.append(node.name)
        elif isinstance(node, BinaryOp):
            visit(node.left)
            visit(node.right)
        elif isinstance(node, UnaryOp):
            visit(node.operand)
        elif isinstance(node, FunctionCall):
            for arg in node.arguments:
                visit(arg)
        elif isinstance(node, IfExpression):
            visit(node.condition)
            visit(node.then_branch)
            visit(node.else_branch)
        elif isinstance(node, PreOp):
            dependencies.append(node.stream_name)
        elif isinstance(node, FoldOp):
            visit(node.stream)
            visit(node.initial)
            visit(node.accumulator.body)

    visit(expr)
    return list(set(dependencies))  # 去重


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
    return False
