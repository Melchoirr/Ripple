"""
Ripple Language - AST 可视化器
支持多种输出格式：ASCII 树、DOT (Graphviz)、JSON
"""

from typing import Any, List, Optional
from ripple_ast import (
    ASTNode, Program, Statement, Expression, TypeNode,
    # 类型节点
    BasicType, ArrayType, StreamType, FunctionType, StructType,
    # 表达式节点
    Literal, Identifier, BinaryOp, UnaryOp, FunctionCall,
    ArrayLiteral, ArrayAccess, StructLiteral, FieldAccess,
    IfExpression, LetExpression, Lambda,
    PreOp, FoldOp, MapOp, FilterOp, ReduceOp,
    # 声明节点
    SourceDecl, StreamDecl, SinkDecl, FuncDecl, TypeDecl
)
import json


class ASTVisualizer:
    """AST 可视化器"""

    def __init__(self):
        self.node_counter = 0

    def visualize(self, node: ASTNode, format: str = "tree") -> str:
        """
        可视化 AST

        Args:
            node: AST 节点
            format: 输出格式 - "tree" (ASCII), "dot" (Graphviz), "json"

        Returns:
            可视化字符串
        """
        if format == "tree":
            return self._to_tree(node)
        elif format == "dot":
            return self._to_dot(node)
        elif format == "json":
            return self._to_json(node)
        else:
            raise ValueError(f"Unknown format: {format}")

    # ==================== ASCII Tree ====================

    def _to_tree(self, node: ASTNode, prefix: str = "", is_last: bool = True) -> str:
        """生成 ASCII 树形图"""
        lines = []

        # 当前节点的连接符
        connector = "└── " if is_last else "├── "

        # 节点标签
        label = self._get_node_label(node)
        lines.append(prefix + connector + label)

        # 子节点的前缀
        child_prefix = prefix + ("    " if is_last else "│   ")

        # 获取子节点
        children = self._get_children(node)

        for i, (child_name, child_node) in enumerate(children):
            is_last_child = (i == len(children) - 1)

            if child_node is None:
                lines.append(child_prefix + ("└── " if is_last_child else "├── ") + f"{child_name}: None")
            elif isinstance(child_node, list):
                # 列表类型的子节点
                list_connector = "└── " if is_last_child else "├── "
                lines.append(child_prefix + list_connector + f"{child_name}: [{len(child_node)} items]")
                list_prefix = child_prefix + ("    " if is_last_child else "│   ")
                for j, item in enumerate(child_node):
                    is_last_item = (j == len(child_node) - 1)
                    if isinstance(item, ASTNode):
                        lines.append(self._to_tree(item, list_prefix, is_last_item))
                    else:
                        item_connector = "└── " if is_last_item else "├── "
                        lines.append(list_prefix + item_connector + repr(item))
            elif isinstance(child_node, dict):
                # 字典类型的子节点
                dict_connector = "└── " if is_last_child else "├── "
                lines.append(child_prefix + dict_connector + f"{child_name}: {{{len(child_node)} fields}}")
                dict_prefix = child_prefix + ("    " if is_last_child else "│   ")
                items = list(child_node.items())
                for j, (key, value) in enumerate(items):
                    is_last_item = (j == len(items) - 1)
                    item_connector = "└── " if is_last_item else "├── "
                    if isinstance(value, ASTNode):
                        lines.append(dict_prefix + item_connector + f"{key}:")
                        inner_prefix = dict_prefix + ("    " if is_last_item else "│   ")
                        lines.append(self._to_tree(value, inner_prefix, True))
                    else:
                        lines.append(dict_prefix + item_connector + f"{key}: {repr(value)}")
            elif isinstance(child_node, ASTNode):
                lines.append(child_prefix + ("└── " if is_last_child else "├── ") + f"{child_name}:")
                inner_prefix = child_prefix + ("    " if is_last_child else "│   ")
                lines.append(self._to_tree(child_node, inner_prefix, True))
            else:
                # 基本类型
                child_connector = "└── " if is_last_child else "├── "
                lines.append(child_prefix + child_connector + f"{child_name}: {repr(child_node)}")

        return "\n".join(lines)

    def _get_node_label(self, node: ASTNode) -> str:
        """获取节点标签"""
        class_name = node.__class__.__name__

        # 为不同节点类型添加关键信息
        if isinstance(node, Literal):
            return f"{class_name}({node.value}, {node.type_name})"
        elif isinstance(node, Identifier):
            return f"{class_name}({node.name})"
        elif isinstance(node, BinaryOp):
            return f"{class_name}({node.operator})"
        elif isinstance(node, UnaryOp):
            return f"{class_name}({node.operator})"
        elif isinstance(node, SourceDecl):
            return f"{class_name}({node.name})"
        elif isinstance(node, StreamDecl):
            trigger_info = f", on={node.trigger}" if node.trigger else ""
            return f"{class_name}({node.name}{trigger_info})"
        elif isinstance(node, SinkDecl):
            return f"{class_name}({node.name})"
        elif isinstance(node, FuncDecl):
            params = ", ".join(node.parameters)
            return f"{class_name}({node.name}({params}))"
        elif isinstance(node, TypeDecl):
            return f"{class_name}({node.name})"
        elif isinstance(node, FunctionCall):
            return f"{class_name}({node.name})"
        elif isinstance(node, FieldAccess):
            return f"{class_name}(.{node.field_name})"
        elif isinstance(node, Lambda):
            params = ", ".join(node.parameters)
            return f"{class_name}(({params}) => ...)"
        elif isinstance(node, PreOp):
            return f"{class_name}"
        elif isinstance(node, FoldOp):
            return f"{class_name}"
        elif isinstance(node, BasicType):
            return f"{class_name}({node.name})"
        elif isinstance(node, ArrayType):
            return f"{class_name}"
        elif isinstance(node, StructType):
            fields = ", ".join(node.fields.keys())
            return f"{class_name}({{{fields}}})"
        else:
            return class_name

    def _get_children(self, node: ASTNode) -> List[tuple]:
        """获取节点的子节点列表，返回 (名称, 节点) 元组列表"""
        children = []

        if isinstance(node, Program):
            children.append(("statements", node.statements))
        elif isinstance(node, SourceDecl):
            if node.type_sig:
                children.append(("type", node.type_sig))
            if node.initial_value:
                children.append(("initial", node.initial_value))
        elif isinstance(node, StreamDecl):
            children.append(("expr", node.expression))
        elif isinstance(node, SinkDecl):
            children.append(("expr", node.expression))
        elif isinstance(node, FuncDecl):
            children.append(("body", node.body))
        elif isinstance(node, TypeDecl):
            children.append(("def", node.type_def))
        elif isinstance(node, BinaryOp):
            children.append(("left", node.left))
            children.append(("right", node.right))
        elif isinstance(node, UnaryOp):
            children.append(("operand", node.operand))
        elif isinstance(node, FunctionCall):
            children.append(("args", node.arguments))
        elif isinstance(node, IfExpression):
            children.append(("cond", node.condition))
            children.append(("then", node.then_branch))
            children.append(("else", node.else_branch))
        elif isinstance(node, LetExpression):
            children.append(("value", node.value))
            children.append(("body", node.body))
        elif isinstance(node, Lambda):
            children.append(("body", node.body))
        elif isinstance(node, PreOp):
            children.append(("stream", node.stream_name))
            children.append(("initial", node.initial_value))
        elif isinstance(node, FoldOp):
            children.append(("init", node.initial_value))
            children.append(("accum", node.accumulator))
        elif isinstance(node, MapOp):
            children.append(("array", node.array))
            children.append(("mapper", node.mapper))
        elif isinstance(node, FilterOp):
            children.append(("array", node.array))
            children.append(("predicate", node.predicate))
        elif isinstance(node, ReduceOp):
            children.append(("array", node.array))
            children.append(("init", node.initial))
            children.append(("accum", node.accumulator))
        elif isinstance(node, ArrayLiteral):
            children.append(("elements", node.elements))
        elif isinstance(node, ArrayAccess):
            children.append(("array", node.array))
            children.append(("index", node.index))
        elif isinstance(node, StructLiteral):
            children.append(("fields", node.fields))
        elif isinstance(node, FieldAccess):
            children.append(("object", node.object))
        elif isinstance(node, ArrayType):
            children.append(("element", node.element_type))
        elif isinstance(node, StructType):
            children.append(("fields", node.fields))
        elif isinstance(node, FunctionType):
            children.append(("params", node.param_types))
            children.append(("return", node.return_type))

        return children

    # ==================== DOT (Graphviz) ====================

    def _to_dot(self, node: ASTNode) -> str:
        """生成 DOT 格式（用于 Graphviz）"""
        self.node_counter = 0
        lines = [
            "digraph AST {",
            "    node [shape=box, fontname=\"Courier\"];",
            "    edge [fontname=\"Courier\", fontsize=10];",
            ""
        ]

        self._add_dot_node(node, lines)

        lines.append("}")
        return "\n".join(lines)

    def _add_dot_node(self, node: ASTNode, lines: List[str], parent_id: Optional[int] = None, edge_label: str = "") -> int:
        """递归添加 DOT 节点"""
        node_id = self.node_counter
        self.node_counter += 1

        # 节点标签
        label = self._get_dot_label(node)
        color = self._get_dot_color(node)
        lines.append(f'    n{node_id} [label="{label}", fillcolor="{color}", style="filled"];')

        # 连接到父节点
        if parent_id is not None:
            if edge_label:
                lines.append(f'    n{parent_id} -> n{node_id} [label="{edge_label}"];')
            else:
                lines.append(f'    n{parent_id} -> n{node_id};')

        # 处理子节点
        children = self._get_children(node)
        for child_name, child_node in children:
            if child_node is None:
                continue
            elif isinstance(child_node, list):
                for i, item in enumerate(child_node):
                    if isinstance(item, ASTNode):
                        self._add_dot_node(item, lines, node_id, f"{child_name}[{i}]")
            elif isinstance(child_node, dict):
                for key, value in child_node.items():
                    if isinstance(value, ASTNode):
                        self._add_dot_node(value, lines, node_id, f"{child_name}.{key}")
            elif isinstance(child_node, ASTNode):
                self._add_dot_node(child_node, lines, node_id, child_name)

        return node_id

    def _get_dot_label(self, node: ASTNode) -> str:
        """获取 DOT 节点标签"""
        label = self._get_node_label(node)
        # 转义特殊字符
        return label.replace('"', '\\"').replace('\n', '\\n')

    def _get_dot_color(self, node: ASTNode) -> str:
        """获取节点颜色"""
        if isinstance(node, (Program,)):
            return "#E8E8E8"  # 灰色 - 程序根节点
        elif isinstance(node, (SourceDecl, StreamDecl, SinkDecl)):
            return "#B3E5FC"  # 浅蓝 - 声明节点
        elif isinstance(node, (FuncDecl, TypeDecl)):
            return "#C8E6C9"  # 浅绿 - 定义节点
        elif isinstance(node, (BinaryOp, UnaryOp)):
            return "#FFE0B2"  # 浅橙 - 运算符
        elif isinstance(node, (Literal, Identifier)):
            return "#FFF9C4"  # 浅黄 - 叶子节点
        elif isinstance(node, (IfExpression, LetExpression)):
            return "#E1BEE7"  # 浅紫 - 控制流
        elif isinstance(node, (PreOp, FoldOp)):
            return "#FFCDD2"  # 浅红 - 时序操作
        elif isinstance(node, (MapOp, FilterOp, ReduceOp)):
            return "#B2DFDB"  # 浅青 - 高阶操作
        elif isinstance(node, (BasicType, ArrayType, StructType)):
            return "#D7CCC8"  # 浅棕 - 类型节点
        else:
            return "#FFFFFF"  # 白色 - 默认

    # ==================== JSON ====================

    def _to_json(self, node: ASTNode) -> str:
        """生成 JSON 格式"""
        return json.dumps(self._node_to_dict(node), indent=2, ensure_ascii=False)

    def _node_to_dict(self, node: ASTNode) -> dict:
        """将节点转换为字典"""
        result = {"_type": node.__class__.__name__}

        children = self._get_children(node)
        for child_name, child_node in children:
            if child_node is None:
                result[child_name] = None
            elif isinstance(child_node, list):
                result[child_name] = [
                    self._node_to_dict(item) if isinstance(item, ASTNode) else item
                    for item in child_node
                ]
            elif isinstance(child_node, dict):
                result[child_name] = {
                    key: self._node_to_dict(value) if isinstance(value, ASTNode) else value
                    for key, value in child_node.items()
                }
            elif isinstance(child_node, ASTNode):
                result[child_name] = self._node_to_dict(child_node)
            else:
                result[child_name] = child_node

        # 添加额外属性
        if isinstance(node, Literal):
            result["value"] = node.value
            result["literal_type"] = node.type_name
        elif isinstance(node, Identifier):
            result["name"] = node.name
        elif isinstance(node, BinaryOp):
            result["operator"] = node.operator
        elif isinstance(node, UnaryOp):
            result["operator"] = node.operator
        elif isinstance(node, SourceDecl):
            result["name"] = node.name
        elif isinstance(node, StreamDecl):
            result["name"] = node.name
            result["trigger"] = node.trigger
        elif isinstance(node, SinkDecl):
            result["name"] = node.name
        elif isinstance(node, FuncDecl):
            result["name"] = node.name
            result["parameters"] = node.parameters
        elif isinstance(node, TypeDecl):
            result["name"] = node.name
        elif isinstance(node, FunctionCall):
            result["name"] = node.name
        elif isinstance(node, FieldAccess):
            result["field"] = node.field_name
        elif isinstance(node, Lambda):
            result["parameters"] = node.parameters
        elif isinstance(node, LetExpression):
            result["var_name"] = node.name
        elif isinstance(node, BasicType):
            result["type_name"] = node.name

        return result


def visualize_ast(code: str, format: str = "tree") -> str:
    """
    可视化 Ripple 代码的 AST

    Args:
        code: Ripple 源代码
        format: 输出格式 - "tree", "dot", "json"

    Returns:
        可视化字符串
    """
    from ripple_lexer import RippleLexer
    from ripple_parser import RippleParser

    lexer = RippleLexer(code)
    tokens = lexer.tokenize()

    parser = RippleParser(tokens)
    ast = parser.parse()

    visualizer = ASTVisualizer()
    return visualizer.visualize(ast, format)


def save_dot_file(code: str, output_path: str):
    """保存 DOT 文件，可用 Graphviz 渲染"""
    dot_content = visualize_ast(code, "dot")
    with open(output_path, 'w') as f:
        f.write(dot_content)
    print(f"DOT 文件已保存到: {output_path}")
    print(f"使用以下命令渲染: dot -Tpng {output_path} -o ast.png")


# ==================== 命令行接口 ====================

if __name__ == "__main__":
    import sys

    # 测试代码
    test_code = """
    type Point = { x: int, y: int };

    source p : Point := { x: 3, y: 4 };
    source scale := 2;

    func square(n) = n * n;

    stream distance <- sqrt(square(p.x) + square(p.y));
    stream scaled <- { x: p.x * scale, y: p.y * scale };

    sink dist_out <- distance;
    sink scaled_out <- scaled;
    """

    # 如果有命令行参数
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        format = sys.argv[2] if len(sys.argv) > 2 else "tree"

        with open(file_path, 'r') as f:
            code = f.read()

        print(visualize_ast(code, format))
    else:
        # 演示模式
        print("=" * 60)
        print("Ripple AST 可视化演示")
        print("=" * 60)

        print("\n源代码:")
        print("-" * 60)
        print(test_code)

        print("\n" + "=" * 60)
        print("ASCII 树形图:")
        print("=" * 60)
        print(visualize_ast(test_code, "tree"))

        print("\n" + "=" * 60)
        print("DOT 格式 (Graphviz):")
        print("=" * 60)
        print(visualize_ast(test_code, "dot"))

        # 保存 DOT 文件
        save_dot_file(test_code, "ast_demo.dot")
