"""
Ripple Language - Parser (语法分析器)
根据 EBNF 规范实现的递归下降解析器
"""

from typing import List, Optional
from ripple_lexer import Token, TokenType, RippleLexer
from ripple_ast import *


class ParseError(Exception):
    """解析错误"""
    pass


class RippleParser:
    """Ripple 语言语法分析器"""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current_token(self) -> Token:
        """获取当前 token"""
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]

    def peek_token(self, offset: int = 1) -> Token:
        """向前查看 token"""
        pos = self.pos + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[pos]

    def advance(self) -> Token:
        """前进一个 token"""
        token = self.current_token()
        if token.type != TokenType.EOF:
            self.pos += 1
        return token

    def expect(self, token_type: TokenType) -> Token:
        """期望特定类型的 token"""
        token = self.current_token()
        if token.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, but got {token.type.name} "
                f"at L{token.line}:C{token.column}"
            )
        return self.advance()

    def match(self, *token_types: TokenType) -> bool:
        """检查当前 token 是否匹配指定类型之一"""
        return self.current_token().type in token_types

    # ================== 解析方法 ==================

    def parse(self) -> Program:
        """解析程序：Program ::= { Statement }"""
        statements = []
        while not self.match(TokenType.EOF):
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        return Program(statements)

    def parse_statement(self) -> Optional[Statement]:
        """
        解析语句：
        Statement ::= SourceDecl | StreamDecl | SinkDecl | FuncDecl | TypeDecl
        """
        if self.match(TokenType.KW_SOURCE):
            return self.parse_source_decl()
        elif self.match(TokenType.KW_STREAM):
            return self.parse_stream_decl()
        elif self.match(TokenType.KW_SINK):
            return self.parse_sink_decl()
        elif self.match(TokenType.KW_FUNC):
            return self.parse_func_decl()
        elif self.match(TokenType.KW_TYPE):
            return self.parse_type_decl()
        else:
            raise ParseError(
                f"Unexpected token {self.current_token().type.name} "
                f"at L{self.current_token().line}:C{self.current_token().column}"
            )

    def parse_source_decl(self) -> SourceDecl:
        """
        解析源声明：
        SourceDecl ::= "source" Identifier ":" TypeSignature [ ":=" Expression ] ";"
                    |  "source" Identifier ":=" Expression ";"
        类型注解可选，但如果省略则必须有初始值
        """
        self.expect(TokenType.KW_SOURCE)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        type_sig = None
        initial_value = None

        # 检查下一个 token 是 ":" (类型注解) 还是 ":=" (直接赋值)
        if self.match(TokenType.COLON):
            # 有类型注解: source name : type ...
            self.advance()
            type_sig = self.parse_type()

            # 可选的初始值
            if self.match(TokenType.OP_SOURCE):
                self.advance()
                initial_value = self.parse_expression()

        elif self.match(TokenType.OP_SOURCE):
            # 无类型注解，直接赋值: source name := value
            self.advance()
            initial_value = self.parse_expression()
            # type_sig 保持 None，由类型推断器处理

        else:
            raise ParseError(
                f"Expected ':' or ':=' after source name at "
                f"L{self.current_token().line}:C{self.current_token().column}"
            )

        self.expect(TokenType.SEMICOLON)

        return SourceDecl(name, type_sig, initial_value)

    def parse_stream_decl(self) -> StreamDecl:
        """
        解析流声明：
        StreamDecl ::= "stream" Identifier "<-" Expression [ "on" Identifier ] ";"
        """
        self.expect(TokenType.KW_STREAM)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        self.expect(TokenType.OP_BIND)
        expression = self.parse_expression()

        # 解析可选的触发器子句（支持字段访问，如 pos.x）
        trigger = None
        if self.match(TokenType.KW_ON):
            self.advance()
            trigger_token = self.expect(TokenType.IDENTIFIER)
            trigger = trigger_token.value
            # 支持字段访问：on pos.x
            while self.match(TokenType.DOT):
                self.advance()
                field_token = self.expect(TokenType.IDENTIFIER)
                trigger = f"{trigger}.{field_token.value}"

        self.expect(TokenType.SEMICOLON)

        # 提取依赖关系和状态信息
        decl = StreamDecl(name, expression, trigger)
        decl.static_dependencies = extract_dependencies(expression)
        decl.is_stateful = is_stateful_expr(expression)

        return decl

    def parse_sink_decl(self) -> SinkDecl:
        """
        解析 Sink 声明：
        SinkDecl ::= "sink" Identifier "<-" Expression ";"
        """
        self.expect(TokenType.KW_SINK)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        self.expect(TokenType.OP_BIND)
        expression = self.parse_expression()

        self.expect(TokenType.SEMICOLON)

        return SinkDecl(name, expression)

    def parse_func_decl(self) -> FuncDecl:
        """
        解析函数声明：
        FuncDecl ::= "func" Identifier "(" [ Identifier { "," Identifier } ] ")" "=" Expression ";"
        """
        self.expect(TokenType.KW_FUNC)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        self.expect(TokenType.LPAREN)
        params = []
        if not self.match(TokenType.RPAREN):
            param_token = self.expect(TokenType.IDENTIFIER)
            params.append(param_token.value)

            while self.match(TokenType.COMMA):
                self.advance()
                param_token = self.expect(TokenType.IDENTIFIER)
                params.append(param_token.value)

        self.expect(TokenType.RPAREN)
        self.expect(TokenType.EQUALS)

        body = self.parse_expression()
        self.expect(TokenType.SEMICOLON)

        return FuncDecl(name, params, body)

    def parse_type_decl(self) -> TypeDecl:
        """
        解析类型定义：
        TypeDecl ::= "type" Identifier "=" StructType ";"
        """
        self.expect(TokenType.KW_TYPE)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        self.expect(TokenType.EQUALS)
        type_def = self.parse_struct_type()

        self.expect(TokenType.SEMICOLON)

        return TypeDecl(name, type_def)

    def parse_struct_type(self) -> StructType:
        """
        解析结构体类型：
        StructType ::= "{" [ Identifier ":" Type { "," Identifier ":" Type } ] "}"
        """
        self.expect(TokenType.LBRACE)
        fields = {}

        if not self.match(TokenType.RBRACE):
            # 第一个字段
            field_name = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.COLON)
            field_type = self.parse_type()
            fields[field_name] = field_type

            # 后续字段
            while self.match(TokenType.COMMA):
                self.advance()
                if self.match(TokenType.RBRACE):
                    break  # 允许尾部逗号
                field_name = self.expect(TokenType.IDENTIFIER).value
                self.expect(TokenType.COLON)
                field_type = self.parse_type()
                fields[field_name] = field_type

        self.expect(TokenType.RBRACE)
        return StructType(fields)

    def parse_type(self) -> TypeNode:
        """
        解析类型：
        TypeSignature ::= BasicType | StreamType | ArrayType | StructType | Identifier
        """
        if self.match(TokenType.TYPE_STREAM):
            self.advance()
            self.expect(TokenType.OP_LT)
            element_type = self.parse_type()
            self.expect(TokenType.OP_GT)
            return StreamType(element_type)
        elif self.match(TokenType.TYPE_INT, TokenType.TYPE_FLOAT,
                        TokenType.TYPE_BOOL, TokenType.TYPE_STRING):
            type_token = self.advance()
            return BasicType(type_token.value)
        elif self.match(TokenType.LBRACKET):
            # 数组类型 [T]
            self.advance()
            element_type = self.parse_type()
            self.expect(TokenType.RBRACKET)
            return ArrayType(element_type)
        elif self.match(TokenType.LBRACE):
            # 内联结构体类型 { x: int, y: int }
            return self.parse_struct_type()
        elif self.match(TokenType.IDENTIFIER):
            # 自定义类型名（如 Point）
            type_token = self.advance()
            return BasicType(type_token.value)  # 作为自定义类型名
        else:
            raise ParseError(f"Expected type at L{self.current_token().line}")

    def parse_expression(self) -> Expression:
        """
        解析表达式（处理运算符优先级）
        Expression ::= LogicalOrExpr
        """
        return self.parse_logical_or()

    def parse_logical_or(self) -> Expression:
        """解析逻辑或表达式"""
        left = self.parse_logical_and()

        while self.match(TokenType.OP_OR):
            op_token = self.advance()
            right = self.parse_logical_and()
            left = BinaryOp(op_token.value, left, right)

        return left

    def parse_logical_and(self) -> Expression:
        """解析逻辑与表达式"""
        left = self.parse_equality()

        while self.match(TokenType.OP_AND):
            op_token = self.advance()
            right = self.parse_equality()
            left = BinaryOp(op_token.value, left, right)

        return left

    def parse_equality(self) -> Expression:
        """解析相等性表达式"""
        left = self.parse_comparison()

        while self.match(TokenType.OP_EQ, TokenType.OP_NEQ):
            op_token = self.advance()
            right = self.parse_comparison()
            left = BinaryOp(op_token.value, left, right)

        return left

    def parse_comparison(self) -> Expression:
        """解析比较表达式"""
        left = self.parse_additive()

        while self.match(TokenType.OP_LT, TokenType.OP_GT,
                         TokenType.OP_LTE, TokenType.OP_GTE):
            op_token = self.advance()
            right = self.parse_additive()
            left = BinaryOp(op_token.value, left, right)

        return left

    def parse_additive(self) -> Expression:
        """解析加减表达式"""
        left = self.parse_multiplicative()

        while self.match(TokenType.OP_PLUS, TokenType.OP_MINUS):
            op_token = self.advance()
            right = self.parse_multiplicative()
            left = BinaryOp(op_token.value, left, right)

        return left

    def parse_multiplicative(self) -> Expression:
        """解析乘除模表达式"""
        left = self.parse_unary()

        while self.match(TokenType.OP_MULT, TokenType.OP_DIV, TokenType.OP_MOD):
            op_token = self.advance()
            right = self.parse_unary()
            left = BinaryOp(op_token.value, left, right)

        return left

    def parse_unary(self) -> Expression:
        """解析一元表达式"""
        if self.match(TokenType.OP_NOT, TokenType.OP_MINUS):
            op_token = self.advance()
            operand = self.parse_unary()
            return UnaryOp(op_token.value, operand)

        return self.parse_postfix()

    def parse_postfix(self) -> Expression:
        """解析后缀表达式（数组索引访问、字段访问）"""
        expr = self.parse_primary()

        # 处理连续的后缀操作：arr[0][1], p.x.y, obj.arr[0]
        while self.match(TokenType.LBRACKET, TokenType.DOT):
            if self.match(TokenType.LBRACKET):
                self.advance()
                index = self.parse_expression()
                self.expect(TokenType.RBRACKET)
                expr = ArrayAccess(expr, index)
            elif self.match(TokenType.DOT):
                self.advance()
                field_name = self.expect(TokenType.IDENTIFIER).value
                expr = FieldAccess(expr, field_name)

        return expr

    def parse_primary(self) -> Expression:
        """
        解析基本表达式：
        Primary ::= Literal | Identifier | FunctionCall | IfExpr | Lambda | "(" Expression ")"
        """
        # 字面量
        if self.match(TokenType.INT_LITERAL):
            token = self.advance()
            return Literal(token.value, 'int')

        if self.match(TokenType.FLOAT_LITERAL):
            token = self.advance()
            return Literal(token.value, 'float')

        if self.match(TokenType.STRING_LITERAL):
            token = self.advance()
            return Literal(token.value, 'string')

        if self.match(TokenType.BOOL_LITERAL):
            token = self.advance()
            return Literal(token.value, 'bool')

        # 数组字面量
        if self.match(TokenType.LBRACKET):
            return self.parse_array_literal()

        # 结构体字面量
        if self.match(TokenType.LBRACE):
            return self.parse_struct_literal()

        # If 表达式
        if self.match(TokenType.KW_IF):
            return self.parse_if_expression()

        # Let 表达式
        if self.match(TokenType.KW_LET):
            return self.parse_let_expression()

        # Pre 操作符
        if self.match(TokenType.ID_PRE):
            return self.parse_pre_op()

        # Fold 操作符
        if self.match(TokenType.ID_FOLD):
            return self.parse_fold_op()

        # Map 操作符
        if self.match(TokenType.ID_MAP):
            return self.parse_map_op()

        # Filter 操作符
        if self.match(TokenType.ID_FILTER):
            return self.parse_filter_op()

        # Reduce 操作符
        if self.match(TokenType.ID_REDUCE):
            return self.parse_reduce_op()

        # Lambda 表达式 或 标识符/函数调用
        if self.match(TokenType.IDENTIFIER):
            name_token = self.advance()
            name = name_token.value

            # 函数调用
            if self.match(TokenType.LPAREN):
                self.advance()
                args = []

                if not self.match(TokenType.RPAREN):
                    args.append(self.parse_expression())
                    while self.match(TokenType.COMMA):
                        self.advance()
                        args.append(self.parse_expression())

                self.expect(TokenType.RPAREN)
                return FunctionCall(name, args)
            else:
                # 标识符
                return Identifier(name)

        # Lambda 表达式：(params) => body
        if self.match(TokenType.LPAREN):
            # 尝试解析 lambda
            saved_pos = self.pos
            try:
                return self.parse_lambda()
            except:
                # 不是 lambda，恢复位置并解析为括号表达式
                self.pos = saved_pos
                self.advance()  # (
                expr = self.parse_expression()
                self.expect(TokenType.RPAREN)
                return expr

        raise ParseError(
            f"Unexpected token {self.current_token().type.name} "
            f"at L{self.current_token().line}:C{self.current_token().column}"
        )

    def parse_if_expression(self) -> IfExpression:
        """
        解析 If 表达式：
        if condition then expr1 else expr2 end
        """
        self.expect(TokenType.KW_IF)
        condition = self.parse_expression()
        self.expect(TokenType.KW_THEN)
        then_branch = self.parse_expression()
        self.expect(TokenType.KW_ELSE)
        else_branch = self.parse_expression()
        self.expect(TokenType.KW_END)

        return IfExpression(condition, then_branch, else_branch)

    def parse_let_expression(self) -> LetExpression:
        """
        解析 Let 表达式：
        let name = value in body
        """
        self.expect(TokenType.KW_LET)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        self.expect(TokenType.EQUALS)
        value = self.parse_expression()

        self.expect(TokenType.KW_IN)
        body = self.parse_expression()

        return LetExpression(name, value, body)

    def parse_pre_op(self) -> PreOp:
        """
        解析 Pre 操作符：
        pre(stream_name, initial_value)
        """
        self.expect(TokenType.ID_PRE)
        self.expect(TokenType.LPAREN)

        stream_name_token = self.expect(TokenType.IDENTIFIER)
        stream_name = stream_name_token.value

        self.expect(TokenType.COMMA)
        initial_value = self.parse_expression()

        self.expect(TokenType.RPAREN)

        return PreOp(stream_name, initial_value)

    def parse_fold_op(self) -> FoldOp:
        """
        解析 Fold 操作符：
        fold(stream, initial, (acc, x) => body)
        """
        self.expect(TokenType.ID_FOLD)
        self.expect(TokenType.LPAREN)

        stream = self.parse_expression()
        self.expect(TokenType.COMMA)

        initial = self.parse_expression()
        self.expect(TokenType.COMMA)

        accumulator = self.parse_lambda()

        self.expect(TokenType.RPAREN)

        return FoldOp(stream, initial, accumulator)

    def parse_lambda(self) -> Lambda:
        """
        解析 Lambda 表达式：
        (param1, param2, ...) => body
        """
        self.expect(TokenType.LPAREN)

        params = []
        if not self.match(TokenType.RPAREN):
            param_token = self.expect(TokenType.IDENTIFIER)
            params.append(param_token.value)

            while self.match(TokenType.COMMA):
                self.advance()
                param_token = self.expect(TokenType.IDENTIFIER)
                params.append(param_token.value)

        self.expect(TokenType.RPAREN)
        self.expect(TokenType.ARROW)

        body = self.parse_expression()

        return Lambda(params, body)

    def parse_array_literal(self) -> ArrayLiteral:
        """
        解析数组字面量：
        [expr1, expr2, ...]
        """
        self.expect(TokenType.LBRACKET)
        elements = []

        if not self.match(TokenType.RBRACKET):
            elements.append(self.parse_expression())
            while self.match(TokenType.COMMA):
                self.advance()
                # 允许尾部逗号
                if self.match(TokenType.RBRACKET):
                    break
                elements.append(self.parse_expression())

        self.expect(TokenType.RBRACKET)
        return ArrayLiteral(elements)

    def parse_struct_literal(self) -> StructLiteral:
        """
        解析结构体字面量：
        { field1: expr1, field2: expr2, ... }
        """
        self.expect(TokenType.LBRACE)
        fields = {}

        if not self.match(TokenType.RBRACE):
            # 第一个字段
            field_name = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.COLON)
            field_value = self.parse_expression()
            fields[field_name] = field_value

            # 后续字段
            while self.match(TokenType.COMMA):
                self.advance()
                if self.match(TokenType.RBRACE):
                    break  # 允许尾部逗号
                field_name = self.expect(TokenType.IDENTIFIER).value
                self.expect(TokenType.COLON)
                field_value = self.parse_expression()
                fields[field_name] = field_value

        self.expect(TokenType.RBRACE)
        return StructLiteral(fields)

    def parse_map_op(self) -> MapOp:
        """
        解析 Map 操作符：
        map(array, (x) => body)
        """
        self.expect(TokenType.ID_MAP)
        self.expect(TokenType.LPAREN)

        array = self.parse_expression()
        self.expect(TokenType.COMMA)

        mapper = self.parse_lambda()

        self.expect(TokenType.RPAREN)
        return MapOp(array, mapper)

    def parse_filter_op(self) -> FilterOp:
        """
        解析 Filter 操作符：
        filter(array, (x) => predicate)
        """
        self.expect(TokenType.ID_FILTER)
        self.expect(TokenType.LPAREN)

        array = self.parse_expression()
        self.expect(TokenType.COMMA)

        predicate = self.parse_lambda()

        self.expect(TokenType.RPAREN)
        return FilterOp(array, predicate)

    def parse_reduce_op(self) -> ReduceOp:
        """
        解析 Reduce 操作符：
        reduce(array, initial, (acc, x) => body)
        """
        self.expect(TokenType.ID_REDUCE)
        self.expect(TokenType.LPAREN)

        array = self.parse_expression()
        self.expect(TokenType.COMMA)

        initial = self.parse_expression()
        self.expect(TokenType.COMMA)

        accumulator = self.parse_lambda()

        self.expect(TokenType.RPAREN)
        return ReduceOp(array, initial, accumulator)


# 测试代码
if __name__ == "__main__":
    test_code = """
    source A : int := 0;
    stream B <- A * 2;
    stream C <- A + 1;
    stream D <- B + C;

    stream counter <- pre(counter, 0) + 1;
    """

    lexer = RippleLexer(test_code)
    tokens = lexer.tokenize()

    parser = RippleParser(tokens)
    ast = parser.parse()

    print("语法分析结果：")
    print("=" * 80)
    print(ast)
    print("\n详细节点：")
    for stmt in ast.statements:
        print(f"\n{stmt}")
        if isinstance(stmt, StreamDecl):
            print(f"  依赖: {stmt.static_dependencies}")
            print(f"  有状态: {stmt.is_stateful}")
