"""
Ripple Language - 类型推断与检查器
自动推断表达式类型，支持省略类型注解
"""

from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass

from ripple_ast import (
    ASTNode, Expression, TypeNode, BasicType, ArrayType, StructType,
    StreamType, FunctionType, Literal, Identifier, BinaryOp, UnaryOp,
    FunctionCall, IfExpression, LetExpression, Lambda, ArrayLiteral,
    ArrayAccess, StructLiteral, FieldAccess, PreOp, FoldOp, MapOp,
    FilterOp, ReduceOp, Program, SourceDecl, StreamDecl, SinkDecl,
    FuncDecl, TypeDecl
)


@dataclass
class TypeError:
    """类型错误"""
    message: str
    location: Optional[str] = None  # 可选的位置信息

    def __repr__(self):
        if self.location:
            return f"TypeError at {self.location}: {self.message}"
        return f"TypeError: {self.message}"


class TypeChecker:
    """类型推断和检查器"""

    def __init__(self):
        # 类型环境：变量名 -> 类型
        self.type_env: Dict[str, TypeNode] = {}
        # 用户定义的类型别名
        self.type_aliases: Dict[str, TypeNode] = {}
        # 用户定义的函数
        self.user_functions: Dict[str, FuncDecl] = {}
        # 收集的类型错误
        self.errors: List[TypeError] = []

        # 内置函数类型签名
        self.builtin_functions: Dict[str, Tuple[List[str], str]] = {
            # 数学函数: (参数类型列表, 返回类型)
            'abs': (['number'], 'number'),  # number = int | float
            'sqrt': (['number'], 'float'),
            'max': (['number', 'number'], 'number'),
            'min': (['number', 'number'], 'number'),

            # 数组函数
            'len': (['array'], 'int'),
            'head': (['array'], 'element'),  # element = 数组元素类型
            'tail': (['array'], 'array'),
            'last': (['array'], 'element'),
            'sum': (['[number]'], 'number'),
            'reverse': (['array'], 'array'),
            'transpose': (['[[any]]'], '[[any]]'),

            # 将来的 CSV 函数
            'load_csv': (['string'], '[[any]]'),
        }

    def check_program(self, program: Program) -> List[TypeError]:
        """检查整个程序的类型"""
        self.errors = []
        self.type_env = {}
        self.type_aliases = {}
        self.user_functions = {}

        # 第一遍：收集类型别名和函数定义
        for stmt in program.statements:
            if isinstance(stmt, TypeDecl):
                self.type_aliases[stmt.name] = stmt.type_def
            elif isinstance(stmt, FuncDecl):
                self.user_functions[stmt.name] = stmt

        # 第二遍：处理源和流声明
        for stmt in program.statements:
            if isinstance(stmt, SourceDecl):
                self._check_source(stmt)
            elif isinstance(stmt, StreamDecl):
                self._check_stream(stmt)
            elif isinstance(stmt, SinkDecl):
                self._check_sink(stmt)

        return self.errors

    def _check_source(self, decl: SourceDecl):
        """检查源声明并推断类型"""
        if decl.type_sig:
            # 有显式类型
            declared_type = self._resolve_type(decl.type_sig)
            self.type_env[decl.name] = declared_type

            # 如果有初始值，检查类型兼容性
            if decl.initial_value:
                inferred_type = self.infer_expression(decl.initial_value)
                if not self._types_compatible(declared_type, inferred_type):
                    self.errors.append(TypeError(
                        f"Source '{decl.name}': declared type {declared_type} "
                        f"incompatible with initial value type {inferred_type}"
                    ))
        else:
            # 没有显式类型，从初始值推断
            if decl.initial_value:
                inferred_type = self.infer_expression(decl.initial_value)
                self.type_env[decl.name] = inferred_type
            else:
                self.errors.append(TypeError(
                    f"Source '{decl.name}': no type annotation and no initial value"
                ))

        # 如果是结构体类型，也添加字段类型
        source_type = self.type_env.get(decl.name)
        if isinstance(source_type, StructType):
            for field_name, field_type in source_type.fields.items():
                self.type_env[f"{decl.name}.{field_name}"] = field_type

    def _check_stream(self, decl: StreamDecl):
        """检查流声明并推断类型"""
        inferred_type = self.infer_expression(decl.expression)
        self.type_env[decl.name] = inferred_type

        # 如果是结构体类型，也添加字段类型
        if isinstance(inferred_type, StructType):
            for field_name, field_type in inferred_type.fields.items():
                self.type_env[f"{decl.name}.{field_name}"] = field_type

    def _check_sink(self, decl: SinkDecl):
        """检查 sink 声明"""
        inferred_type = self.infer_expression(decl.expression)
        self.type_env[decl.name] = inferred_type

    def infer_expression(self, expr: Expression, local_env: Dict[str, TypeNode] = None) -> TypeNode:
        """推断表达式类型"""
        if local_env is None:
            local_env = {}

        # 合并环境
        env = {**self.type_env, **local_env}

        if isinstance(expr, Literal):
            return self._infer_literal(expr)

        elif isinstance(expr, Identifier):
            return self._infer_identifier(expr, env)

        elif isinstance(expr, BinaryOp):
            return self._infer_binary_op(expr, local_env)

        elif isinstance(expr, UnaryOp):
            return self._infer_unary_op(expr, local_env)

        elif isinstance(expr, FunctionCall):
            return self._infer_function_call(expr, local_env)

        elif isinstance(expr, IfExpression):
            return self._infer_if_expression(expr, local_env)

        elif isinstance(expr, LetExpression):
            return self._infer_let_expression(expr, local_env)

        elif isinstance(expr, ArrayLiteral):
            return self._infer_array_literal(expr, local_env)

        elif isinstance(expr, ArrayAccess):
            return self._infer_array_access(expr, local_env)

        elif isinstance(expr, StructLiteral):
            return self._infer_struct_literal(expr, local_env)

        elif isinstance(expr, FieldAccess):
            return self._infer_field_access(expr, local_env)

        elif isinstance(expr, PreOp):
            return self._infer_pre_op(expr, local_env)

        elif isinstance(expr, FoldOp):
            return self._infer_fold_op(expr, local_env)

        elif isinstance(expr, MapOp):
            return self._infer_map_op(expr, local_env)

        elif isinstance(expr, FilterOp):
            return self._infer_filter_op(expr, local_env)

        elif isinstance(expr, ReduceOp):
            return self._infer_reduce_op(expr, local_env)

        elif isinstance(expr, Lambda):
            # Lambda 类型推断需要上下文，返回 any
            return BasicType('any')

        else:
            return BasicType('any')

    def _infer_literal(self, lit: Literal) -> TypeNode:
        """推断字面量类型"""
        type_map = {
            'int': BasicType('int'),
            'float': BasicType('float'),
            'bool': BasicType('bool'),
            'string': BasicType('string'),
        }
        return type_map.get(lit.type_name, BasicType('any'))

    def _infer_identifier(self, ident: Identifier, env: Dict[str, TypeNode]) -> TypeNode:
        """推断标识符类型"""
        if ident.name in env:
            return env[ident.name]
        # 未知类型，返回 any
        return BasicType('any')

    def _infer_binary_op(self, op: BinaryOp, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断二元运算符类型"""
        left_type = self.infer_expression(op.left, local_env)
        right_type = self.infer_expression(op.right, local_env)

        # 比较运算符返回 bool
        if op.operator in ('==', '!=', '<', '>', '<=', '>='):
            return BasicType('bool')

        # 逻辑运算符返回 bool
        if op.operator in ('&&', '||'):
            return BasicType('bool')

        # 算术运算符
        if op.operator in ('+', '-', '*'):
            return self._arithmetic_result_type(left_type, right_type)

        # 除法总是返回 float
        if op.operator == '/':
            return BasicType('float')

        # 取模返回 int
        if op.operator == '%':
            return BasicType('int')

        return BasicType('any')

    def _arithmetic_result_type(self, t1: TypeNode, t2: TypeNode) -> TypeNode:
        """计算算术运算结果类型"""
        t1_name = self._get_basic_type_name(t1)
        t2_name = self._get_basic_type_name(t2)

        # float 参与运算结果为 float
        if t1_name == 'float' or t2_name == 'float':
            return BasicType('float')

        # 两个 int 结果为 int
        if t1_name == 'int' and t2_name == 'int':
            return BasicType('int')

        return BasicType('any')

    def _get_basic_type_name(self, t: TypeNode) -> str:
        """获取基本类型名"""
        if isinstance(t, BasicType):
            return t.name
        return 'any'

    def _infer_unary_op(self, op: UnaryOp, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断一元运算符类型"""
        operand_type = self.infer_expression(op.operand, local_env)

        if op.operator == '!':
            return BasicType('bool')

        if op.operator == '-':
            return operand_type

        return operand_type

    def _infer_function_call(self, call: FunctionCall, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断函数调用类型"""
        # 检查是否是内置函数
        if call.name in self.builtin_functions:
            return self._infer_builtin_call(call, local_env)

        # 检查是否是用户定义函数
        if call.name in self.user_functions:
            return self._infer_user_function_call(call, local_env)

        return BasicType('any')

    def _infer_builtin_call(self, call: FunctionCall, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断内置函数调用类型"""
        func_sig = self.builtin_functions[call.name]
        param_types, return_type = func_sig

        # 特殊处理需要根据参数推断返回类型的函数
        if return_type == 'number':
            # 返回类型取决于参数
            if call.arguments:
                arg_type = self.infer_expression(call.arguments[0], local_env)
                return arg_type
            return BasicType('int')

        if return_type == 'element':
            # 返回数组元素类型
            if call.arguments:
                array_type = self.infer_expression(call.arguments[0], local_env)
                if isinstance(array_type, ArrayType):
                    return array_type.element_type
            return BasicType('any')

        if return_type == 'array':
            # 返回同类型数组
            if call.arguments:
                return self.infer_expression(call.arguments[0], local_env)
            return ArrayType(BasicType('any'))

        # 直接返回类型
        return BasicType(return_type.replace('[', '').replace(']', '').replace('any', 'any'))

    def _infer_user_function_call(self, call: FunctionCall, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断用户函数调用类型"""
        func_decl = self.user_functions[call.name]

        # 构建函数体的局部环境
        func_env = {}
        for i, param in enumerate(func_decl.parameters):
            if i < len(call.arguments):
                func_env[param] = self.infer_expression(call.arguments[i], local_env)
            else:
                func_env[param] = BasicType('any')

        # 推断函数体类型
        return self.infer_expression(func_decl.body, func_env)

    def _infer_if_expression(self, expr: IfExpression, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断 if 表达式类型"""
        then_type = self.infer_expression(expr.then_branch, local_env)
        else_type = self.infer_expression(expr.else_branch, local_env)

        # 返回更通用的类型
        return self._common_type(then_type, else_type)

    def _infer_let_expression(self, expr: LetExpression, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断 let 表达式类型"""
        value_type = self.infer_expression(expr.value, local_env)
        new_env = {**local_env, expr.name: value_type}
        return self.infer_expression(expr.body, new_env)

    def _infer_array_literal(self, lit: ArrayLiteral, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断数组字面量类型"""
        if not lit.elements:
            return ArrayType(BasicType('any'))

        # 推断第一个元素类型
        elem_type = self.infer_expression(lit.elements[0], local_env)

        # 检查所有元素是否兼容
        for elem in lit.elements[1:]:
            elem_t = self.infer_expression(elem, local_env)
            elem_type = self._common_type(elem_type, elem_t)

        return ArrayType(elem_type)

    def _infer_array_access(self, access: ArrayAccess, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断数组访问类型"""
        array_type = self.infer_expression(access.array, local_env)

        if isinstance(array_type, ArrayType):
            return array_type.element_type

        return BasicType('any')

    def _infer_struct_literal(self, lit: StructLiteral, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断结构体字面量类型"""
        fields = {}
        for field_name, field_expr in lit.fields.items():
            fields[field_name] = self.infer_expression(field_expr, local_env)
        return StructType(fields)

    def _infer_field_access(self, access: FieldAccess, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断字段访问类型"""
        obj_type = self.infer_expression(access.object, local_env)

        if isinstance(obj_type, StructType):
            if access.field_name in obj_type.fields:
                return obj_type.fields[access.field_name]

        # 尝试从环境中查找完整路径
        if isinstance(access.object, Identifier):
            full_path = f"{access.object.name}.{access.field_name}"
            env = {**self.type_env, **local_env}
            if full_path in env:
                return env[full_path]

        return BasicType('any')

    def _infer_pre_op(self, op: PreOp, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断 pre 操作类型"""
        # pre 返回初始值的类型或流的类型
        return self.infer_expression(op.initial_value, local_env)

    def _infer_fold_op(self, op: FoldOp, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断 fold 操作类型"""
        # fold 返回累加器类型
        return self.infer_expression(op.initial, local_env)

    def _infer_map_op(self, op: MapOp, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断 map 操作类型"""
        array_type = self.infer_expression(op.array, local_env)

        if isinstance(array_type, ArrayType) and isinstance(op.mapper, Lambda):
            # 推断 lambda 返回类型
            if op.mapper.parameters:
                lambda_env = {**local_env, op.mapper.parameters[0]: array_type.element_type}
                result_type = self.infer_expression(op.mapper.body, lambda_env)
                return ArrayType(result_type)

        return ArrayType(BasicType('any'))

    def _infer_filter_op(self, op: FilterOp, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断 filter 操作类型"""
        # filter 返回相同类型的数组
        return self.infer_expression(op.array, local_env)

    def _infer_reduce_op(self, op: ReduceOp, local_env: Dict[str, TypeNode]) -> TypeNode:
        """推断 reduce 操作类型"""
        # reduce 返回累加器类型
        return self.infer_expression(op.initial, local_env)

    def _resolve_type(self, type_node: TypeNode) -> TypeNode:
        """解析类型（处理类型别名）"""
        if isinstance(type_node, BasicType):
            if type_node.name in self.type_aliases:
                return self.type_aliases[type_node.name]
        return type_node

    def _types_compatible(self, declared: TypeNode, inferred: TypeNode) -> bool:
        """检查两个类型是否兼容"""
        # any 类型与任何类型兼容
        if self._get_basic_type_name(declared) == 'any':
            return True
        if self._get_basic_type_name(inferred) == 'any':
            return True

        # 相同基本类型
        if isinstance(declared, BasicType) and isinstance(inferred, BasicType):
            if declared.name == inferred.name:
                return True
            # int 可以隐式转换为 float
            if declared.name == 'float' and inferred.name == 'int':
                return True

        # 数组类型
        if isinstance(declared, ArrayType) and isinstance(inferred, ArrayType):
            return self._types_compatible(declared.element_type, inferred.element_type)

        # 结构体类型
        if isinstance(declared, StructType) and isinstance(inferred, StructType):
            if set(declared.fields.keys()) != set(inferred.fields.keys()):
                return False
            for field_name in declared.fields:
                if not self._types_compatible(declared.fields[field_name],
                                               inferred.fields[field_name]):
                    return False
            return True

        return False

    def _common_type(self, t1: TypeNode, t2: TypeNode) -> TypeNode:
        """找到两个类型的共同类型"""
        t1_name = self._get_basic_type_name(t1)
        t2_name = self._get_basic_type_name(t2)

        # 如果有 any，返回另一个
        if t1_name == 'any':
            return t2
        if t2_name == 'any':
            return t1

        # int 和 float -> float
        if (t1_name == 'int' and t2_name == 'float') or \
           (t1_name == 'float' and t2_name == 'int'):
            return BasicType('float')

        # 相同类型
        if t1_name == t2_name:
            return t1

        # 数组类型
        if isinstance(t1, ArrayType) and isinstance(t2, ArrayType):
            return ArrayType(self._common_type(t1.element_type, t2.element_type))

        return BasicType('any')

    def get_type(self, name: str) -> Optional[TypeNode]:
        """获取变量的类型"""
        return self.type_env.get(name)

    def infer_from_value(self, value: Any) -> TypeNode:
        """从运行时值推断类型（用于 CSV 等场景）"""
        if isinstance(value, bool):
            return BasicType('bool')
        elif isinstance(value, int):
            return BasicType('int')
        elif isinstance(value, float):
            return BasicType('float')
        elif isinstance(value, str):
            return BasicType('string')
        elif isinstance(value, list):
            if not value:
                return ArrayType(BasicType('any'))
            elem_type = self.infer_from_value(value[0])
            return ArrayType(elem_type)
        elif isinstance(value, dict):
            fields = {k: self.infer_from_value(v) for k, v in value.items()}
            return StructType(fields)
        return BasicType('any')


# ================== 测试 ==================

if __name__ == "__main__":
    from ripple_lexer import RippleLexer
    from ripple_parser import RippleParser

    test_code = """
    source x : int := 1;
    source y := 3.14;

    stream sum <- x + y;
    stream arr <- [x, x * 2, x * 3];
    stream first <- arr[0];
    stream doubled <- map(arr, (n) => n * 2);

    sink output <- sum;
    """

    lexer = RippleLexer(test_code)
    tokens = lexer.tokenize()

    parser = RippleParser(tokens)
    ast = parser.parse()

    checker = TypeChecker()
    errors = checker.check_program(ast)

    print("类型推断结果:")
    print("=" * 60)
    for name, type_node in checker.type_env.items():
        print(f"  {name}: {type_node}")

    if errors:
        print("\n类型错误:")
        for error in errors:
            print(f"  {error}")
    else:
        print("\n无类型错误!")
