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
        Statement ::= SourceDecl | StreamDecl | SinkDecl
        """
        if self.match(TokenType.KW_SOURCE):
            return self.parse_source_decl()
        elif self.match(TokenType.KW_STREAM):
            return self.parse_stream_decl()
        elif self.match(TokenType.KW_SINK):
            return self.parse_sink_decl()
        else:
            raise ParseError(
                f"Unexpected token {self.current_token().type.name} "
                f"at L{self.current_token().line}:C{self.current_token().column}"
            )

    def parse_source_decl(self) -> SourceDecl:
        """
        解析源声明：
        SourceDecl ::= "source" Identifier ":" TypeSignature [ ":=" Expression ] ";"
        """
        self.expect(TokenType.KW_SOURCE)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        self.expect(TokenType.COLON)
        type_sig = self.parse_type()

        initial_value = None
        if self.match(TokenType.OP_SOURCE):
            self.advance()
            initial_value = self.parse_expression()

        self.expect(TokenType.SEMICOLON)

        return SourceDecl(name, type_sig, initial_value)

    def parse_stream_decl(self) -> StreamDecl:
        """
        解析流声明：
        StreamDecl ::= "stream" Identifier "<-" Expression ";"
        """
        self.expect(TokenType.KW_STREAM)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        self.expect(TokenType.OP_BIND)
        expression = self.parse_expression()

        self.expect(TokenType.SEMICOLON)

        # 提取依赖关系和状态信息
        decl = StreamDecl(name, expression)
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

    def parse_type(self) -> TypeNode:
        """
        解析类型：
        TypeSignature ::= BasicType | StreamType
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

        return self.parse_primary()

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

        # If 表达式
        if self.match(TokenType.KW_IF):
            return self.parse_if_expression()

        # Pre 操作符
        if self.match(TokenType.ID_PRE):
            return self.parse_pre_op()

        # Fold 操作符
        if self.match(TokenType.ID_FOLD):
            return self.parse_fold_op()

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
