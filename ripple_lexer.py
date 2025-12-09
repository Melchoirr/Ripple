"""
Ripple Language - Lexer (词法分析器)
根据 Ripple 语言设计报告实现的词法分析器
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


class TokenType(Enum):
    # 关键字
    KW_STREAM = "stream"
    KW_SOURCE = "source"
    KW_SINK = "sink"
    KW_LIFT = "lift"
    KW_IF = "if"
    KW_THEN = "then"
    KW_ELSE = "else"
    KW_END = "end"
    KW_MATCH = "match"
    KW_WITH = "with"

    # 特殊操作符
    OP_BIND = "<-"           # 流式绑定符
    OP_SOURCE = ":="         # 源定义符
    OP_PIPE = "~>"           # 流向操作符

    # 时序操作符
    ID_PRE = "pre"           # 访问前一时刻的值
    ID_FOLD = "fold"         # 状态累积

    # 基本操作符
    OP_PLUS = "+"
    OP_MINUS = "-"
    OP_MULT = "*"
    OP_DIV = "/"
    OP_MOD = "%"
    OP_EQ = "=="
    OP_NEQ = "!="
    OP_LT = "<"
    OP_GT = ">"
    OP_LTE = "<="
    OP_GTE = ">="
    OP_AND = "&&"
    OP_OR = "||"
    OP_NOT = "!"

    # 分隔符
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    COMMA = ","
    SEMICOLON = ";"
    COLON = ":"
    ARROW = "=>"

    # 类型
    TYPE_INT = "int"
    TYPE_FLOAT = "float"
    TYPE_BOOL = "bool"
    TYPE_STRING = "string"
    TYPE_STREAM = "Stream"

    # 字面量和标识符
    IDENTIFIER = "IDENTIFIER"
    INT_LITERAL = "INT_LITERAL"
    FLOAT_LITERAL = "FLOAT_LITERAL"
    STRING_LITERAL = "STRING_LITERAL"
    BOOL_LITERAL = "BOOL_LITERAL"

    # 特殊
    EOF = "EOF"
    NEWLINE = "NEWLINE"


@dataclass
class Token:
    type: TokenType
    value: any
    line: int
    column: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:C{self.column})"


class RippleLexer:
    """Ripple 语言词法分析器"""

    # 关键字映射
    KEYWORDS = {
        'stream': TokenType.KW_STREAM,
        'source': TokenType.KW_SOURCE,
        'sink': TokenType.KW_SINK,
        'lift': TokenType.KW_LIFT,
        'if': TokenType.KW_IF,
        'then': TokenType.KW_THEN,
        'else': TokenType.KW_ELSE,
        'end': TokenType.KW_END,
        'match': TokenType.KW_MATCH,
        'with': TokenType.KW_WITH,
        'pre': TokenType.ID_PRE,
        'fold': TokenType.ID_FOLD,
        'int': TokenType.TYPE_INT,
        'float': TokenType.TYPE_FLOAT,
        'bool': TokenType.TYPE_BOOL,
        'string': TokenType.TYPE_STRING,
        'Stream': TokenType.TYPE_STREAM,
        'true': TokenType.BOOL_LITERAL,
        'false': TokenType.BOOL_LITERAL,
    }

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def current_char(self) -> Optional[str]:
        """获取当前字符"""
        if self.pos >= len(self.source):
            return None
        return self.source[self.pos]

    def peek_char(self, offset: int = 1) -> Optional[str]:
        """向前查看字符"""
        pos = self.pos + offset
        if pos >= len(self.source):
            return None
        return self.source[pos]

    def advance(self) -> Optional[str]:
        """前进一个字符"""
        if self.pos >= len(self.source):
            return None
        char = self.source[self.pos]
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def skip_whitespace(self):
        """跳过空白字符（除换行符）"""
        while self.current_char() and self.current_char() in ' \t\r':
            self.advance()

    def skip_comment(self):
        """跳过注释（支持单行注释 //）"""
        if self.current_char() == '/' and self.peek_char() == '/':
            while self.current_char() and self.current_char() != '\n':
                self.advance()

    def read_number(self) -> Token:
        """读取数字（整数或浮点数）"""
        start_line = self.line
        start_col = self.column
        num_str = ""
        has_dot = False

        while self.current_char() and (self.current_char().isdigit() or self.current_char() == '.'):
            if self.current_char() == '.':
                if has_dot:
                    break
                has_dot = True
            num_str += self.current_char()
            self.advance()

        if has_dot:
            return Token(TokenType.FLOAT_LITERAL, float(num_str), start_line, start_col)
        else:
            return Token(TokenType.INT_LITERAL, int(num_str), start_line, start_col)

    def read_string(self) -> Token:
        """读取字符串"""
        start_line = self.line
        start_col = self.column
        self.advance()  # 跳过开始的引号

        string_value = ""
        while self.current_char() and self.current_char() != '"':
            if self.current_char() == '\\':
                self.advance()
                escape_char = self.current_char()
                if escape_char == 'n':
                    string_value += '\n'
                elif escape_char == 't':
                    string_value += '\t'
                elif escape_char == '\\':
                    string_value += '\\'
                elif escape_char == '"':
                    string_value += '"'
                else:
                    string_value += escape_char
                self.advance()
            else:
                string_value += self.current_char()
                self.advance()

        if self.current_char() == '"':
            self.advance()  # 跳过结束的引号

        return Token(TokenType.STRING_LITERAL, string_value, start_line, start_col)

    def read_identifier(self) -> Token:
        """读取标识符或关键字"""
        start_line = self.line
        start_col = self.column
        identifier = ""

        while self.current_char() and (self.current_char().isalnum() or self.current_char() == '_'):
            identifier += self.current_char()
            self.advance()

        # 检查是否是关键字
        token_type = self.KEYWORDS.get(identifier, TokenType.IDENTIFIER)

        # 布尔字面量特殊处理
        if token_type == TokenType.BOOL_LITERAL:
            value = True if identifier == 'true' else False
            return Token(token_type, value, start_line, start_col)

        return Token(token_type, identifier, start_line, start_col)

    def tokenize(self) -> List[Token]:
        """执行词法分析，返回 token 列表"""
        while self.pos < len(self.source):
            self.skip_whitespace()

            if not self.current_char():
                break

            # 跳过注释
            if self.current_char() == '/' and self.peek_char() == '/':
                self.skip_comment()
                continue

            start_line = self.line
            start_col = self.column
            char = self.current_char()

            # 换行符
            if char == '\n':
                self.advance()
                continue

            # 数字
            if char.isdigit():
                self.tokens.append(self.read_number())
                continue

            # 字符串
            if char == '"':
                self.tokens.append(self.read_string())
                continue

            # 标识符和关键字
            if char.isalpha() or char == '_':
                self.tokens.append(self.read_identifier())
                continue

            # 多字符操作符
            two_char = char + (self.peek_char() or '')

            if two_char == '<-':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OP_BIND, '<-', start_line, start_col))
                continue

            if two_char == ':=':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OP_SOURCE, ':=', start_line, start_col))
                continue

            if two_char == '~>':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OP_PIPE, '~>', start_line, start_col))
                continue

            if two_char == '==':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OP_EQ, '==', start_line, start_col))
                continue

            if two_char == '!=':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OP_NEQ, '!=', start_line, start_col))
                continue

            if two_char == '<=':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OP_LTE, '<=', start_line, start_col))
                continue

            if two_char == '>=':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OP_GTE, '>=', start_line, start_col))
                continue

            if two_char == '&&':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OP_AND, '&&', start_line, start_col))
                continue

            if two_char == '||':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OP_OR, '||', start_line, start_col))
                continue

            if two_char == '=>':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.ARROW, '=>', start_line, start_col))
                continue

            # 单字符操作符
            single_char_tokens = {
                '+': TokenType.OP_PLUS,
                '-': TokenType.OP_MINUS,
                '*': TokenType.OP_MULT,
                '/': TokenType.OP_DIV,
                '%': TokenType.OP_MOD,
                '<': TokenType.OP_LT,
                '>': TokenType.OP_GT,
                '!': TokenType.OP_NOT,
                '(': TokenType.LPAREN,
                ')': TokenType.RPAREN,
                '{': TokenType.LBRACE,
                '}': TokenType.RBRACE,
                ',': TokenType.COMMA,
                ';': TokenType.SEMICOLON,
                ':': TokenType.COLON,
            }

            if char in single_char_tokens:
                self.advance()
                self.tokens.append(Token(single_char_tokens[char], char, start_line, start_col))
                continue

            # 未知字符
            raise SyntaxError(f"未知字符 '{char}' 在 L{start_line}:C{start_col}")

        # 添加 EOF token
        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens


# 测试代码
if __name__ == "__main__":
    # 测试代码示例
    test_code = """
    // 声明一个输入源
    source A : int := 0;

    // 声明计算流
    stream B <- A * 2;
    stream C <- A + 1;
    stream D <- B + C;

    // 使用 pre 操作符
    stream counter <- pre(counter, 0) + 1;

    // 使用 fold
    stream sum <- fold(numbers, 0, (acc, x) => acc + x);
    """

    lexer = RippleLexer(test_code)
    tokens = lexer.tokenize()

    print("词法分析结果：")
    print("=" * 80)
    for token in tokens:
        print(token)
