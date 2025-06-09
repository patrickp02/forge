import re
from typing import List, Tuple, NamedTuple

# === Token Definitions ===

class Token(NamedTuple):
    type: str
    value: str
    line: int
    column: int

# === Token Specifications ===

TOKEN_SPEC = [
    # Multi-char ops first
    ("COMMENT",   r'#.*'),
    ("FATARROW",  r'=>'),       # Simplified function bodies: fn x => x + 1
    ("ARROW",     r'->'),       # Type annotations: fn greet() -> str
    ("INC",       r'\+\+'),
    ("DEC",       r'--'),

    ("EQEQ",      r'=='),       # Equality
    ("NEQ",       r'!='),       # Not equal
    ("LTE",       r'<='),       # Less than or equal
    ("GTE",       r'>='),       # Greater than or equal
    ("AND",       r'&&'),       # Logical AND
    ("OR",        r'\|\|'),     # Logical OR
    ("AMP",       r'&'),
    # Single-char ops
    ("EQ",        r'='),
    ("LT",        r'<'),
    ("GT",        r'>'),
    ("NOT",       r'!'),
    ("PLUS",      r'\+'),
    ("MINUS",     r'-'),
    ("MUL",       r'\*'),
    ("DIV",       r'/'),
    ("MOD",       r'%'),
    ("AT",        r'@'),
    ("POW",       r'\^'),



    # Literals
    ("FLOAT",      r"\d+\.\d+"),
    ("NUMBER",    r'\d+(\.\d+)?'),        # Integers & floats
    ("STRING",    r'"(?:\\.|[^"\\])*"'),
    
  # String with escapes

    # Identifiers & keywords
    ("ID",        r'[A-Za-z_][A-Za-z_0-9]*'),

    # Separators
    ("LPAREN",    r'\('),
    ("RPAREN",    r'\)'),
    ("LBRACE",    r'\{'),
    ("RBRACE",    r'\}'),
    ("LBRACKET",  r'\['),
    ("RBRACKET",  r'\]'),
    ("COLON",     r':'),
    ("COMMA",     r','),
    ("DOT",       r'\.'),
    ("SEMI",      r';'),

    # Control
    ("NEWLINE",   r'\n'),
    ("SKIP",      r'[ \t]+'),

    
]


TYPES = {"int", "str", "bool", "any", "list", "StringList", "TokenList", "Token", "token", "Node", "pointer","float", "arr"}
KEYWORDS = {
    "let", "fn", "return", "if", "else", "elif", "while", "for",
    "break", "continue", "match", "default", "true", "false", "null",
    "struct", "attempt", "rescue", "read", "write", "addto", "load"
}




MASTER_PATTERN = re.compile('|'.join(
    f'(?P<{name}>{pattern})' for name, pattern in TOKEN_SPEC
))

# === Lexer Class ===

class Lexer:
    def __init__(self, source: str):
        self.source = source

    def tokenize(self) -> List[Token]:
        line_num = 1
        line_start = 0
        tokens = []

        for mo in MASTER_PATTERN.finditer(self.source):
            kind = mo.lastgroup
            value = mo.group()
            column = mo.start() - line_start

            if kind == "NEWLINE":
                line_num += 1
                line_start = mo.end()
                continue

            elif kind == "SKIP" or kind == "COMMENT":
                continue

            # Promote ID to keyword if matched
            if kind == "ID":
                if value in KEYWORDS:
                    kind = value.upper()
                elif value in TYPES:
                    kind = "TYPE"
            # for token in tokens:
            #      print(token)

            tokens.append(Token(kind, value, line_num, column))

        return tokens
