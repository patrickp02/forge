from lexer import Token, Lexer
print("[LOADED] forge_parser.py from:", __file__)

            # AST Node Classes #


class ASTNode: pass

class AddressOf:
    def __init__(self, expr):
        self.expr = expr

class LoadStmt:
    def __init__(self, path):
        self.path = path


class ErrorDef(ASTNode):
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields


class AttemptRescue(ASTNode):
    def __init__(self, try_block, error_name, rescue_block):
        self.try_block = try_block
        self.error_name = error_name
        self.rescue_block = rescue_block

class AttemptRescueExpr(ASTNode):
    def __init__(self, try_expr, error_name, rescue_expr):
        self.try_expr = try_expr
        self.error_name = error_name
        self.rescue_expr = rescue_expr


class TryExpr(ASTNode):
    def __init__(self, expr, fallback):
        self.expr = expr
        self.fallback = fallback


class NullLiteral(ASTNode):
    pass


class BreakStatement(ASTNode):
    pass


class StructDef(ASTNode):
    def __init__(self, name, fields):  # fields: list of (name, type)
        self.name = name
        self.fields = fields


class StructInstance(ASTNode):
    def __init__(self, struct_name, args):
        self.struct_name = struct_name
        self.args = args


class StructValue:
    def __init__(self, fields):
        self.fields = fields  # dict


class Block(ASTNode):
    def __init__(self, statements):
        self.statements = statements


class MemberAccess(ASTNode):
    def __init__(self, obj, name):
        self.obj = obj    
        self.name = name  


class Program(ASTNode):
    def __init__(self, statements): self.statements = statements


class Assignment(ASTNode):
    def __init__(self, target, expr):
        self.target = target  # Can be a string (ID) or a MemberAccess
        self.expr = expr


class ReadFile(ASTNode):
    def __init__(self, path_expr):
        self.path_expr = path_expr

# class WriteFile(ASTNode):
#     def __init__(self, path_expr, content_expr, spacing_expr=None):
#         self.path_expr = path_expr
#         self.content_expr = content_expr
#         self.spacing_expr = spacing_expr or NumberLiteral(0)

# class AddToFile(ASTNode):
#     def __init__(self, path_expr, content_expr, spacing_expr=None):
#         self.path_expr = path_expr
#         self.content_expr = content_expr
#         self.spacing_expr = spacing_expr or NumberLiteral(0)


class ReturnStatement(ASTNode):
    def __init__(self, expr): self.expr = expr


class FunctionDef(ASTNode):
    def __init__(self, name, params, body, return_type=None):
        self.name = name
        self.params = params
        self.body = body
        self.return_type = return_type  
        print("FUNC: " , name, "return type is", return_type)


class IfExpr(ASTNode):
    def __init__(self, condition, then_branch, elif_branches, else_branch):
        self.condition = condition
        self.then_branch = then_branch
        self.elif_branches = elif_branches
        self.else_branch = else_branch


class WhileLoop(ASTNode):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body


class Expression(ASTNode): pass


class ForStatement(ASTNode):
    def __init__(self, init, condition, increment, body):
        self.init = init
        self.condition = condition
        self.increment = increment
        self.body = body


class ListLiteral(ASTNode):
    def __init__(self, elements):
        self.elements = elements


class ExternExpr(ASTNode):
    def __init__(self, name, arg_types, return_type="int"):
        self.name = name         # function name as string
        self.arg_types = arg_types
        self.return_type = return_type or "int"
        print(f"[DEBUG] ExternExpr created: {name}, args={arg_types}, return_type={return_type}")


class SubscriptExpr(ASTNode):
    def __init__(self, target, index):
        self.target = target
        self.index = index


class UnaryExpr(ASTNode):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class LetStatement(ASTNode):
    def __init__(self, name, expr, type_hint=None):
        self.name = name
        self.expr = expr
        self.type_hint = type_hint

    def __repr__(self):
        return f"Let({self.name} = {self.expr})"


class ExpressionStatement(ASTNode):
    def __init__(self, expr):
        self.expr = expr


class ArrayLiteral(ASTNode):
    def __init__(self, elements):
        self.elements = elements


class PropertyAccess(ASTNode):
    def __init__(self, object_expr, prop):
        self.object = object_expr
        self.prop = prop


class BinaryExpr(Expression):
    def __init__(self, left, op, right): self.left, self.op, self.right = left, op, right


class NumberLiteral(Expression):
    def __init__(self, value): 
        self.value = value
        self.is_float = isinstance(value, float)


class StringLiteral(Expression):
    def __init__(self, value): self.value = value


class Identifier(Expression):
    def __init__(self, name): self.name = name


class CallExpr(Expression):
    def __init__(self, func, args):
        self.func = func
        self.args = args
        print(f"[DEBUG] CallExpr created: {repr(func)} with args = {[type(arg).__name__ for arg in args]}")


class PostfixExpr(ASTNode):
    def __init__(self, operand, op):
        self.operand = operand
        self.op = op

                            # PARSER
# ──────────────────────────────────────────────────────────────#

class Parser:
    
    PRECEDENCE = {
    "OR": 0,
    "AND": 1,
    "EQEQ": 2, "NEQ": 2,
    "LT": 3, "LTE": 3, "GT": 3, "GTE": 3,
    "PLUS": 4, "MINUS": 4, "POW":4,
    "MUL": 5, "DIV": 5, "MOD": 5
    }

    
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0


    def peek(self, offset=0):
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return None


    def is_at_end(self):
        return self.pos >= len(self.tokens)


    def advance(self):
        if not self.is_at_end():
            self.pos += 1
        return self.tokens[self.pos - 1]

    
    def parse_unary(self):
        tok = self.current()
        if tok:
            if tok.type == "AMP":
                self.consume()
                operand = self.parse_unary()
                return AddressOf(operand)

            elif tok.type == "NOT":
                self.consume()
                operand = self.parse_unary()
                return UnaryExpr("!", operand)
            elif tok.type == "MINUS":
                self.consume()
                operand = self.parse_unary()
                return UnaryExpr("-", operand)
            elif tok.type == "ATTEMPT":
                self.consume()
                try_expr = self.parse_unary()
                self.expect("RESCUE")
                rescue_expr = self.parse_unary()
                return AttemptRescueExpr(try_expr, "err", rescue_expr)
        return self.parse_primary()


    def consume_expect(self, expected_type, message="Expected token."):
        if self.check(expected_type):
            return self.advance()
        raise Exception(f"{message} Got: {self.peek().type}")


    def prev(self):
        return self.tokens[self.pos - 1]

    
    def check(self, token_type):
        if self.is_at_end():
            return False
        return self.peek().type == token_type


    def consume(self):
        if self.pos < len(self.tokens):
            self.pos += 1


    def parse_list_literal(self):
        self.expect("LPAREN")
        elements = []
        if not self.check("RPAREN"):
            elements.append(self.parse_expr())
            while self.match("COMMA"):
                elements.append(self.parse_expr())
        self.expect("RPAREN")
        return ListLiteral(elements)


    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None


    def match(self, *types):
        tok = self.current()
        if tok and tok.type in types:
            self.pos += 1
            return tok
        return None
    

    def check_ahead_is_list(self):
        next_tok = self.peek(1)
        return next_tok and next_tok.type in {"NUMBER", "STRING", "TRUE", "FALSE", "ID", "LPAREN"}
    

    def parse_simple_expr(self):
        # No binary/postfix parsing — just literals and identifiers
        tok = self.current()
        if tok.type == "STRING":
            self.consume()
            return StringLiteral(tok.value[1:-1])
        elif tok.type == "NUMBER":
            self.consume()
            return NumberLiteral(float(tok.value) if '.' in tok.value else int(tok.value))
        elif tok.type == "ID":
            self.consume()
            return Identifier(tok.value)
        else:
            raise SyntaxError(f"Expected simple expression, got {tok}")

    
    def parse_struct(self):
        name = self.expect("ID").value
        self.expect("LBRACE")
        fields = []
        while not self.check("RBRACE"):
            field_name = self.expect("ID").value
            self.expect("COLON")
            type_token = self.current()
            if type_token.type in {"TYPE"}:
                self.consume()
                type_name = type_token.value
            else:
                raise SyntaxError(f"Expected type, got {type_token}")
            fields.append((field_name, type_name))
        self.expect("RBRACE")
        return StructDef(name, fields)
    

    def parse_attempt(self):
        try_block = self.parse_block()
        self.expect("RESCUE")
        err_name = self.expect("ID").value
        catch_block = self.parse_block()
        return AttemptRescue(try_block, err_name, catch_block)


    def expect(self, typ):
        tok = self.match(typ)
        if not tok:
            raise SyntaxError(f"Expected {typ}, got {self.current()}")
        return tok


    def parse(self):
        stmts = []
        while self.current():
            stmt = self.parse_stmt()
            if stmt:
                stmts.append(stmt)
        return Program(stmts)


    def parse_stmt(self):
        if self.match("STRUCT"):
            return self.parse_struct()
        if self.match("ATTEMPT"):
            return self.parse_attempt()
        if self.match("FOR"):
            return self.parse_for_stmt()
        elif self.match("LET"):
            #self.expect("LET")
            name = self.expect("ID").value
            type_hint = None
            if self.match("COLON"):
                #self.expect("COLON")
                type_hint = self.expect("TYPE").value  # <- unified handling
            self.expect("EQ")
            expr = self.parse_expr()
            if isinstance(expr, CallExpr) and isinstance(expr.func, Identifier) and expr.func.name == "input":
                expr._expected_type = type_hint
            if isinstance(expr, ListLiteral):
                expr._forced_type_hint = type_hint

            return LetStatement(name, expr, type_hint)

        elif self.match("FN"):
            return self.parse_fn()
        elif self.match("IF"):
            return self.parse_if()        
        elif self.check("ID") and self.peek().type == "LPAREN":
            # Might be extern(...) or any function call
            expr = self.parse_expr()
            if isinstance(expr, ExternExpr):
                return ExpressionStatement(expr)
            return ExpressionStatement(expr)
        elif self.match("WHILE"):
            return self.parse_while()
        elif self.match("RETURN"):
            expr = self.parse_expr()
            return ReturnStatement(expr)
        elif self.match("LBRACE"):
            return self.parse_block()
        elif self.match("BREAK"):
            return BreakStatement()
        elif self.match("LOAD"):
            path_token = self.expect("STRING")
            return LoadStmt(path_token.value[1:-1])  # strips surrounding quotes
        elif self.match("WRITE"):
            self.expect("LPAREN")
            path = self.parse_expr()
            self.expect("COMMA")
            content = self.parse_expr()
            if self.match("COMMA"):
                spacing = self.parse_expr()
            else:
                spacing = NumberLiteral(0)
            self.expect("RPAREN")
            return ExpressionStatement(CallExpr(Identifier("write"), [path, content, spacing]))
        elif self.match("ADDTO"):
            self.expect("LPAREN")
            path = self.parse_expr()
            self.expect("COMMA")
            content = self.parse_expr()
            if self.match("COMMA"):
                spacing = self.parse_expr()
            else:
                spacing = NumberLiteral(0)
            self.expect("RPAREN")
            return ExpressionStatement(CallExpr(Identifier("addto"), [path, content, spacing]))

        elif self.current() and self.current().type == "ID":
            id_token = self.current()
            next_token = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
            if next_token and next_token.type == "EQ":
                self.consume()
                self.consume()
                expr = self.parse_expr()
                return Assignment(id_token.value, expr)
            expr = self.parse_expr()
            return ExpressionStatement(expr)
        elif (id_tok := self.match("ID")) and self.match("EQ"):
            expr = self.parse_expr()
            return Assignment(id_tok.value, expr)
        else:
            expr = self.parse_expr()
            return ExpressionStatement(expr)

        
    def parse_array_literal(self):
        self.expect("LBRACKET")
        elements = []
        if not self.check("RBRACKET"):
            elements.append(self.parse_expr())
            while self.match("COMMA"):
                elements.append(self.parse_expr())
        self.expect("RBRACKET")
        return ArrayLiteral(elements)
    
    def parse_type(self):
        if self.match("AMP"):
            tok = self.expect_any("ID", "TYPE")
            return "&" + tok.value

        tok = self.expect_any("ID", "TYPE")
        return tok.value




    def parse_fn(self):
        name = self.expect("ID").value
        self.expect("LPAREN")
        params = []
        while not self.match("RPAREN"):
            ident = self.expect("ID").value
            if self.match("COLON"):
                type_hint = self.parse_type()
            else:
                type_hint = None
            
            params.append((ident, type_hint))
            self.match("COMMA")
        if self.match("ARROW"):
            type_tok = self.current()
            if type_tok.type in {"TYPE", "ID"}:
                self.consume()
                ret_type = type_tok.value
            else:
                raise SyntaxError(f"Expected type after '->', got {type_tok}")
        else:
            ret_type = None
        if self.match("FATARROW"):
            body = self.parse_expr()
            return FunctionDef(name, params, body, ret_type)
        body = self.parse_block()
        return FunctionDef(name, params, body, ret_type)


    def parse_if(self):
        condition = self.parse_expr()
        then_branch = self.parse_block()  # <--- This already handles LBRACE and RBRACE
        elif_branches = []
        else_branch = None
        while self.match("ELSE"):
            if self.match("IF"):
                cond = self.parse_expr()
                body = self.parse_block()
                elif_branches.append((cond, body))
            else:
                else_branch = self.parse_block()
                break
        return IfExpr(condition, then_branch, elif_branches, else_branch)


    def parse_while(self):
        condition = self.parse_expr()
        body = self.parse_block()  # ← handles { and }
        return WhileLoop(condition, body)


    def parse_block(self):
        self.expect("LBRACE")
        statements = []
        while self.current() and self.current().type != "RBRACE":
            statements.append(self.parse_stmt())
        self.expect("RBRACE")
        return Block(statements)

    
    def check(self, typ):
        tok = self.current()
        return tok is not None and tok.type == typ


    def parse_expr(self):
        # Parse the left-hand side first (could be a variable or member access)
        expr = self.parse_binary()
        # Handle assignment (lowest precedence)
        
        if self.match("EQ"):
            # Must be something assignable: variable or object.field
            if not isinstance(expr, (Identifier, MemberAccess)):
                raise SyntaxError("Invalid assignment target")
            value = self.parse_expr()
            return Assignment(expr, value)
        return expr
# ✅ ensure postfix gets included

    
    # def parse_list_literal(self):
    #     self.expect("LPAREN")

    #     elements = []
    #     if not self.check("RPAREN"):
    #         elements.append(self.parse_expr())  
    #         while self.match("COMMA"):
    #             elements.append(self.parse_expr())  
    #     self.expect("RPAREN")
    #     return ListLiteral(elements)
    
    def parse_postfix(self, expr):
        while True:
            tok = self.current()
            if tok is None:
                break
            if tok.type == "LBRACKET":
                self.consume()
                index = self.parse_expr()
                self.expect("RBRACKET")
                expr = SubscriptExpr(expr, index)
            elif tok.type == "DOT":
                self.consume()
                name_token = self.expect("ID")
                expr = MemberAccess(expr, name_token.value)  # ✅ ALLOW ANY expr
            elif tok.type == "INC" or tok.type == "DEC":
                self.consume()
                expr = PostfixExpr(expr, tok.type)
            elif tok.type == "LPAREN":
                self.consume()
                args = []
                if not self.check("RPAREN"):
                    args.append(self.parse_expr())
                    while self.match("COMMA"):
                        args.append(self.parse_expr())
                self.expect("RPAREN")
                expr = CallExpr(expr, args)
            else:
                break
        return expr


    def parse_for_stmt(self):
        #self.expect("FOR")
        if self.match("LET"):
            name = self.expect("ID").value
            # Handle optional type annotation
            if self.match("COLON"):
                type_tok = self.expect("TYPE") if self.check("TYPE") else self.expect("ID")
                type_hint = type_tok.value
            else:
                type_hint = None
            self.expect("EQ")
            init_expr = self.parse_expr()
            init = LetStatement(name, init_expr, type_hint)
        self.expect("SEMI")
        condition = self.parse_expr()
        self.expect("SEMI")
        increment = self.parse_expr()
        print("[DEBUG] about to parse for-loop body, current token:", self.current())
        body = self.parse_block()
        print("[DEBUG] For-loop init:", init)
        print("[DEBUG] For-loop condition:", type(condition).__name__, repr(condition))
        print("[DEBUG] For-loop increment:", type(increment).__name__, repr(increment))
        return ForStatement(init, condition, increment, body)


    def parse_binary(self, precedence=0):
        left = self.parse_unary()
        left = self.parse_postfix(left)
        while True:
            tok = self.current()
            if not tok or tok.type not in self.PRECEDENCE:
                break
            tok_prec = self.PRECEDENCE[tok.type]
            if tok_prec < precedence:
                break
            op = tok.type
            self.consume()
            right = self.parse_binary(tok_prec + 1)
            right = self.parse_postfix(right)
            left = BinaryExpr(left, op, right)
        return left


    def expect_any(self, *types):
        tok = self.current()
        if tok and tok.type in types:
            return self.advance()
        raise SyntaxError(f"Expected one of {types}, got {tok}")


    def parse_primary(self):
        tok = self.current()
        if tok is None:
            raise SyntaxError("Unexpected end of input in primary expression")
        if self.check("ID") and self.current().value == "extern" and self.peek(1) and self.peek(1).type == "LPAREN":
            self.consume()
            self.expect("LPAREN")
            name_tok = self.expect("STRING")
            name = name_tok.value.strip('"')
            arg_types = []
            while not self.check("RPAREN"):
                if self.match("COMMA"):
                    continue
                arg_tok = self.expect_any("ID","TYPE")
                arg_types.append(arg_tok.value)
            self.expect("RPAREN")
            # ✅ Look ahead for optional -> return_type
            return_type = "int"
            if self.match("ARROW"):   # handles ->
                if self.match("TYPE"):
                    return_type_tok = self.prev()
                else:
                    return_type_tok = self.expect("ID")
                return_type = return_type_tok.value
            return ExternExpr(name, arg_types, return_type)
        
        elif tok.type == "ID":
            self.consume()
            expr = Identifier(tok.value)
            while True:
                if self.match("DOT"):
                    prop_token = self.consume_expect("ID", "Expected property name after '.'")
                    expr = MemberAccess(expr, prop_token.value)

                elif self.match("LBRACK"):
                    index = self.parse_expr()
                    self.expect("RBRACK")
                    expr = SubscriptExpr(expr, index)

                elif self.match("LPAREN"):
                    args = []
                    if not self.check("RPAREN"):
                        args.append(self.parse_expr())
                        while self.match("COMMA"):
                            args.append(self.parse_expr())
                    self.expect("RPAREN")
                    expr = CallExpr(expr, args)
                else:
                    break
            print("[DEBUG] Built primary expr node:", type(expr).__name__, repr(expr))
            return expr
        elif tok.type == "TYPE":
            self.consume()
            return self.prev().value
        elif tok.type == "TRUE":
            self.consume()
            return NumberLiteral(1)
        elif tok.type == "FALSE":
            self.consume()
            return NumberLiteral(0)
        elif tok.type == "NULL":
            self.consume()
            return NullLiteral()
        elif tok.type == "READ":
            self.consume()
            self.expect("LPAREN")
            path = self.parse_expr()
            self.expect("RPAREN")
            return ExpressionStatement(CallExpr(Identifier("read"), [path]))
        elif tok.type == "AT":
            self.consume()
            return self.parse_list_literal()
        elif tok.type == "LPAREN":
            self.consume()
            expr = self.parse_expr()
            self.expect("RPAREN")
            return expr
        elif tok.type == "LBRACKET":
            return self.parse_array_literal()
        elif tok.type == "STRING":
            self.consume()
            value = bytes(tok.value[1:-1], "utf-8").decode("unicode_escape")
            return StringLiteral(value)
        elif tok.type == "NUMBER":
            self.consume()
            return NumberLiteral(float(tok.value) if '.' in tok.value else int(tok.value))
        elif tok.type == "FLOAT":
            self.consume()
            return NumberLiteral(float(tok.value))
        # elif tok.type == "INT":
        #     self.consume()
        #     return tok.value
        raise SyntaxError(f"Unexpected token in primary: {tok}")
    

