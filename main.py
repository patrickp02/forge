print("RUNNING MAIN")

from lexer import Lexer
from forge_parser import Parser
from interpreter import Interpreter
from forge_parser import ExpressionStatement
import sys

def run_code(source_code):
    # print("Source Code:")
    # print(source_code)

    # Tokenize
    lexer = Lexer(source_code)
    tokens = lexer.tokenize()
    # print("\nTokens:")
    # for t in tokens:
    #     print(t)

    # Parse to AST
    parser = Parser(tokens)
    ast = parser.parse()
    # print("\nAST:")
    # print(ast)

    # Interpret
    print("\nRunning Interpreter...")
    interp = Interpreter()
    interp.eval(ast)
    return ast 


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: forge <source_file.forge>")
        sys.exit(1)

    filename = sys.argv[1]
    with open(filename, "r") as f:
        code = f.read()
    ast = run_code(code)

    # print("\nAST:")
    # for stmt in ast.statements:
    #     print("[AST Statement]", type(stmt), repr(stmt))
    #     if isinstance(stmt, ExpressionStatement):
    #         print("  ↳ Inner expression:", type(stmt.expr), repr(stmt.expr))

