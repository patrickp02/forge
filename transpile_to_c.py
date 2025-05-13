import sys
from lexer import Lexer
from forge_parser import (
    Parser,
    Program,
    LetStatement,
    StringLiteral,
    NumberLiteral,
    Identifier,
    CallExpr,
    ExpressionStatement,
    BinaryExpr,
    Assignment,
    ForStatement,
    ListLiteral,
    SubscriptExpr,
    MemberAccess,
    PostfixExpr,
    AttemptRescue,
    StructDef,
    StructInstance,
    LoadStmt,
    UnaryExpr,
    ArrayLiteral,
    NullLiteral,
    FunctionDef,
    ReturnStatement,
    BreakStatement,
    ExternExpr,
    PropertyAccess,
    AttemptRescueExpr,
    AddressOf
)
from jinja2 import Environment, FileSystemLoader
import os
import subprocess
import platform

env = Environment(loader=FileSystemLoader("templates"))
def escape_c_string(s):
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
class CTranspiler:
    def __init__(self):
        self.includes = [] 
        self.loaded_modules = set()
        self.body_lines = []
        self.function_types = {}  # fn_name -> "int", "string", etc.
        self.temp_counter = 0
        self.code = []
        self.indent_level = 0
        self.struct_defs = {}
        self.defined_structs = set()  # Track struct type names
        self.defined_functions = set()
        self.global_scope = {}
        self.types = {}  # maps variable/function names to types
        self.externs = {}  # { "socket": ["int", "int", "int", "int"], ... }
        self.module_search_paths = ["./", "./modules/", "./lib/"]
        self.scope_stack = [self.global_scope]
        self.functions = []


    def set_type(self, name, type_):
        if self.scope_stack:
            self.scope_stack[-1][name] = type_
        else:
            self.global_scope[name] = type_

    def write_line(self, line: str):
        indent_space = "    " * self.indent_level
        self.code.append(f"{indent_space}{line}")

    def push_scope(self):
        self.scope_stack.append({})

    def pop_scope(self):
        self.scope_stack.pop()
    
    def in_function(self):
        return len(self.scope_stack) > 0

    def declare_var(self, name, typ):
        if typ == "array" and self.in_function():
            self.types[name] = "array"     # use as pointer
        elif typ == "array":
            self.types[name] = "array_value"  # top-level let
        else:
            self.types[name] = typ

    def _safe_gen_expr(self, expr):
        # prevent nesting another AttemptRescueExpr within itself
        if isinstance(expr, AttemptRescueExpr):
            result_var = self._attempt_expr_cache.get(id(expr))
            if result_var:
                return result_var, "int"
            raise Exception("Nested AttemptRescueExpr is not allowed")
        return self.gen_expr(expr)

    def is_declared(self, name):
        return any(name in scope for scope in reversed(self.scope_stack))

    def get_type(self, name):
        for i, scope in enumerate(reversed(self.scope_stack)):
            if name in scope:
                print(f"[DEBUG] get_type({name}) -> {scope[name]} [scope depth {-i}]")
                return scope[name]
        print(f"[DEBUG] get_type({name}) -> NOT FOUND in any scope")
        return "unknown"

    def gen_BreakStatement(self, node):
        self.body_lines.append("break;")
    
    def new_temp(self, prefix="tmp"):
        self.temp_counter += 1
        return f"_{prefix}_{self.temp_counter}"
    
    def add_include(self, include):
        if include not in self.includes:
            self.includes.add(include)
            
    RESERVED_C_KEYWORDS = {"auto", "break", "case", "char", "const", "continue", "default",
                       "do", "double", "else", "enum", "extern", "float", "for", "goto",
                       "if", "inline", "int", "long", "register", "restrict", "return",
                       "short", "signed", "sizeof", "static", "struct", "switch", "typedef",
                       "union", "unsigned", "void", "volatile", "while"}

    def sanitize_name(self, name):
        stdlib_conflicts = {"pow", "sqrt", "floor", "ceil", "round"}
        if name in self.RESERVED_C_KEYWORDS or name in stdlib_conflicts:
            return f"forge_{name}"
        return name
    
    def gen_ForStatement(self, node):
        self.push_scope()  # Start loop scope
        # Init: must be let-style
        if isinstance(node.init, LetStatement):
            init_code, init_type = self.gen_expr(node.init.expr)
            var_type = self.map_type(init_type)
            var_name = node.init.name
            print(f"[DEBUG] Let: {node.init.name}, Inferred Type: {var_type}, Code: {init_code}")

            if not self.is_declared(var_name):
                self.declare_var(var_name, init_type)
                init = f"{var_type} {var_name} = {init_code}"
                self.scope_stack[-1][var_name] = init_type
            else:
                init = f"{var_name} = {init_code}"
        else:
            raise NotImplementedError("Only let-style for loop inits are supported")

        # Condition
        condition_code, _ = self.gen_expr(node.condition)

        # Increment
        if isinstance(node.increment, Assignment):
            if isinstance(node.increment.target, str):
                lhs = node.increment.target
            else:
                lhs = node.increment.target.name
            rhs_code, _ = self.gen_expr(node.increment.expr)
            update = f"{lhs} = {rhs_code}"

        elif isinstance(node.increment, PostfixExpr):
            expr_code, _ = self.gen_expr(node.increment.operand)
            if node.increment.op == "INC":
                update = f"{expr_code}++"
            elif node.increment.op == "DEC":
                update = f"{expr_code}--"
            else:
                raise NotImplementedError(f"Unknown postfix op: {node.increment.op}")
        else:
            raise NotImplementedError("Only assignment-style or postfix increments supported")

        # Body
        body_code = self.transpile_block(node.body)

        self.pop_scope()  # End loop scope

        # Render
        tpl = env.get_template("for_statement.c.j2")
        rendered = tpl.render(init=init, condition=condition_code, update=update, body=body_code)
        self.body_lines.append(rendered)


    def transpile(self, node):
        if isinstance(node, FunctionDef):
            self.add_include('<stdio.h>')
            self.add_include('<stdlib.h>')
            self.add_include('<stddef.h>')
            self.add_include('<time.h>')
            # Custom Headers
            self.add_include('"fileio.h"')
            self.add_include('"array.h"')
            self.add_include('"list.h"')
            self.add_include('"hash.h"')
            self.add_include('"runtime.h"')
            # Socket programming headers 
            self.add_include('<sys/socket.h>')
            self.add_include('<netinet/in.h>')
            self.add_include('<arpa/inet.h>')
            self.add_include('<unistd.h>')  # for close()
            
        elif isinstance(node, BreakStatement):
            return self.gen_BreakStatement(node)

        method = getattr(self, f"gen_{type(node).__name__}", None)
        if method:
            return method(node)
        raise NotImplementedError(f"No transpiler for {type(node).__name__}")
    
    def gen_Program(self, node: Program):
        self.includes = set()
        self.scope_stack = [{}]  # Use clean new scope for tracking vars
        self.functions = []      # Hold generated functions
        self.body_lines = []
        if "net.forge" in self.loaded_modules:
            self.includes.update([
                "#include <sys/socket.h>",
                "#include <arpa/inet.h>",
                "#include <unistd.h>",
                "#include <netinet/in.h>",
                "#include <sys/socket.h>",
                "#include <netinet/in.h>",
                "#include <arpa/inet.h>",

            ])

        for name, args in self.externs.items():
            arg_list = ", ".join(self.map_type(a) for a in args)
            self.header_lines.append(f"extern int {name}({arg_list});")

        # Pre-register all struct names so map_type can resolve early
        for stmt in node.statements:
            if isinstance(stmt, StructDef):
                self.defined_structs.add(stmt.name)

        # Transpile all statements — populates global scope
        for stmt in node.statements:
            self.transpile(stmt)
    
        # Collect struct definitions
        struct_decls = []
        for struct_name, struct_def in self.struct_defs.items():
            struct_lines = [f"typedef struct {struct_name} {{"]
            for field_name, forge_type in struct_def.fields:
                c_type = self.map_type(forge_type)
                struct_lines.append(f"    {c_type} {field_name};")
            struct_lines.append(f"}} {struct_name};\n")
            struct_decls.append("\n".join(struct_lines))
    
        # Collect global declarations AFTER transpile
        global_decls = []
        for name, typ in self.global_scope.items():
            if typ == "list":
                global_decls.append(f"List {name};")
            elif typ == "float":
                global_decls.append(f"double {name};")
            elif typ == "int":
                global_decls.append(f"int {name};")
            elif typ == "bool":
                global_decls.append(f"int {name};")
            elif typ == "string":
                global_decls.append(f"char* {name};")
            else:
                global_decls.append(f"{typ} {name};")
    
        # Put declarations at the top of main
        self.body_lines = global_decls + self.body_lines
    
        includes = [
            '#include <stdio.h>',
            '#include <stdlib.h>',
            '#include "list.h"',
            '#include "exception.h"',
            '#include "fileio.h"',
            '#include "hash.h"',
            '#include "array.h"',
            '#include <stddef.h>',
            '#include <time.h>',
            '#include "runtime.h"',
            "#include <sys/socket.h>",
            "#include <arpa/inet.h>",
            "#include <unistd.h>",
            "#include <netinet/in.h>",
            
        ]
    
        main_template = env.get_template("main.c.j2")
        main_code = main_template.render(body="\n".join(self.body_lines))
    
        # Combine everything
        return "\n".join(includes + [""] + struct_decls + [""] + self.functions + [""] + [main_code])

    def gen_LetStatement(self, node):
        expr = node.expr
        if isinstance(expr, ExpressionStatement):
            expr = expr.expr
        if isinstance(node.expr, ListLiteral):
            type_hint = "list"
            inferred_type = "list"
        result = self.gen_expr(expr)
        self.body_lines.extend(self.code)
        self.code.clear()
        if node.type_hint:
            inferred_type = getattr(node, 'type_hint', None)
        else:
            # Infer type from the expression if not explicitly provided
            if isinstance(node.name, NumberLiteral):
                inferred_type = "int" if not node.value.is_float else "float"
            elif isinstance(node.name, StringLiteral):
                inferred_type = "string"
            elif isinstance(node.name, ListLiteral):
                inferred_type = "list"
            else:
                inferred_type = "unknown"  # Default fallback

        if isinstance(result, tuple) and len(result) == 2:
            value_code, inferred_type = result
        else:
            raise Exception(f"gen_expr did not return (code, type) for: {type(expr).__name__}")

        var_type = self.map_type(inferred_type)
        if inferred_type in ("int",  "bool") and var_type == "string":
            tmp = self.new_temp()
            end = self.new_temp()
            self.body_lines.append(f"char* {end};")
            self.body_lines.append(f"{inferred_type} {tmp} = strtol({value_code}, &{end}, 10);")
            value_code = tmp

        if node.name not in self.scope_stack[-1]:
            self.set_type(node.name, inferred_type)
            print(f"[DEBUG] Declared variable: {node.name}, Type: {inferred_type}")
            # Decide correct C code based on actual Forge type or function return
            if inferred_type == "array_value":
                self.body_lines.append(f"Array {node.name} = {value_code};")
            elif inferred_type == "array":
                self.body_lines.append(f"Array* {node.name} = {value_code};")
            elif inferred_type in self.struct_defs:
                self.body_lines.append(f"{inferred_type} {node.name} = {value_code};")
            elif isinstance(node.expr, CallExpr):
                # Covers both Identifier and PropertyAccess or MemberAccess
                func_name = getattr(node.expr.func, "name", None)
                if isinstance(node.expr.func, Identifier):
                    func_name = node.expr.func.name
                elif hasattr(node.expr.func, "prop"):
                    func_name = f"{node.expr.func.object.name}_{node.expr.func.prop}"
                    print(f"[DEBUG] CallExpr func resolved: {func_name}")
                    print(f"[DEBUG] function_types[{func_name}] = {self.function_types.get(func_name)}")

                ret_type_key = self.function_types.get(func_name)
                if ret_type_key is None:
                    print(f"[WARN] Missing return type for {func_name}, defaulting to inferred_type = {inferred_type}")
                    ret_type_key = inferred_type

                ret_type = self.map_type(ret_type_key)
                print(f"[DEBUG] Declaring {node.name} from {func_name} → {ret_type}")
                print(f"[DEBUG] gen_LetStatement assigning from function: {func_name}")
                print(f"[DEBUG] Raw return type from function_types: {ret_type_key}")
                print(f"[DEBUG] C type after map_type: {ret_type}")

                self.body_lines.append(f"{ret_type} {node.name} = {value_code};")

            else:
                self.body_lines.append(f"{var_type} {node.name} = {value_code};")


    def gen_StructDef(self, node):
        # Cache the struct definition for later lookups (e.g., member access, instantiation)
        self.struct_defs[node.name] = node        
        struct_lines = [f"typedef struct {node.name} {{"]
        for field_name, forge_type in node.fields:
            c_type = self.map_type(forge_type)
            struct_lines.append(f"    {c_type} {field_name};")
        struct_lines.append(f"}} {node.name};\n")
    
        # Do not append struct definitions to body_lines; they will be handled in gen_Program

    def gen_IfExpr(self, node):
        condition, _ = self.gen_expr(node.condition)
        then_body = self.transpile_block(node.then_branch)
        
        elifs = []
        for cond_expr, block in node.elif_branches:
            cond_str, _ = self.gen_expr(cond_expr)
            body_str = self.transpile_block(block)
            elifs.append({"condition": cond_str, "body": body_str})
        
        else_body = None
        if node.else_branch:
            else_body = self.transpile_block(node.else_branch)

        tpl = env.get_template("if_statement.c.j2")
        self.body_lines.append(tpl.render(condition=condition, then_body=then_body, elifs=elifs, else_body=else_body))

    def gen_WhileLoop(self, node):
        condition, _ = self.gen_expr(node.condition)
        body = self.transpile_block(node.body)
        tpl = env.get_template("while_statement.c.j2")
        self.body_lines.append(tpl.render(condition=condition, body=body))

    def gen_CallExpr(self, node):
       # --- Handle method-style and module function calls ---
        print("Entering")
        if isinstance(node.func, MemberAccess):            
            obj_code, obj_type = self.gen_expr(node.func.obj)
            method_name = node.func.name
            args = [self.gen_expr(arg)[0] for arg in node.args]

            if obj_type == "array_value":
                if method_name == "free":
                    return f"array_free(&{obj_code})", "void"

            # 🔧 Move list method logic to the top
            elif obj_type == "list":
                if method_name == "add":
                    el_code, el_type = self.gen_expr(node.args[0])
                    if el_type == "string":
                        return f"list_add_str(&{obj_code}, {el_code})", "void"
                    else:
                        return f"list_add(&{obj_code}, {el_code})", "void"

                elif method_name == "remove":
                    return f"list_remove(&{obj_code}, {args[0]})", "void"

                elif method_name == "index":
                    return f"list_index(&{obj_code}, {args[0]})", "int"
                elif method_name == "free":
                    return f"list_free(&{obj_code})", "void"
                
            elif obj_type == "StringList":
                if method_name == "add":
                    return f"string_list_add(&{obj_code}, {args[0]})", "void"
                elif method_name == "remove":
                    # StringList remove is not defined in your runtime yet! Optional.
                    raise Exception("StringList does not support 'remove' yet")
                elif method_name == "index":
                    # StringList index not defined either. Optional.
                    raise Exception("StringList does not support 'index' yet")
                elif method_name == "free":
                    return f"string_list_free(&{obj_code})", "void"

            # Module-style function calls (math.sum -> math_sum)
            if isinstance(node.func.obj, Identifier):
                module_name = node.func.obj.name
                full_name = f"{module_name}_{method_name}"
                if full_name in self.defined_functions:
                    return f"{full_name}({', '.join(args)})", self.function_types.get(full_name, "int")

                else:    
                    print(f"[WARN] Function '{full_name}' not found in defined_functions")
                    return f"{full_name}({', '.join(args)})", "unknown"

            # Other unsupported member access
            raise Exception(f"Unsupported call on object of type: {obj_type}")

        if isinstance(node.func, Identifier) and node.func.name == "hash":
            arg_expr, arg_type = self.gen_expr(node.args[0])
            tmp = self.new_temp()
            self.body_lines.append(f"char {tmp}[65];")
            self.body_lines.append(f"hash_string({arg_expr}, {tmp});")
            return tmp, "string"

        if isinstance(node.func, PropertyAccess):
            obj_code, obj_type = self.gen_expr(node.func.object)
            method_name = node.func.prop
            args = [self.gen_expr(arg)[0] for arg in node.args]

            # You can treat it the same as MemberAccess for now (or delegate to the same logic)
                # Example: If it's module-style like net.connect -> net_connect
            if isinstance(node.func.object, Identifier):
                module_name = node.func.object.name
                func_call = f"{module_name}_{method_name}({', '.join(args)})"
                return func_call, "int"  # You can improve the return type inference later

            raise Exception(f"Unsupported property access: {obj_type}.{method_name}")

        # Handle identifier-style calls (print, input, struct, user fn)
        if isinstance(node.func, Identifier):
            name = node.func.name
            # if name in self.struct_defs:
            # # --- Handle struct literal construction ---
            #     fields = []
            #     for arg in node.args:
            #         expr_code, _ = self.gen_expr(arg)
            #         fields.append(expr_code)
            #     return f"{{ {', '.join(fields)} }}", name
            # Special return types for certain built-ins
            if name == "token_list_create":
                return "token_list_create()", "TokenList"
            if name == "token_list_add":
                args = [self.gen_expr(arg)[0] for arg in node.args]
                return f"token_list_add(&{args[0]}, {args[1]})", "int"
            if name == "token_list_free":
                args = [self.gen_expr(arg)[0] for arg in node.args]
                return f"token_list_free(&{args[0]})", "void"
            if name == "token_list_get":
                args = [self.gen_expr(arg)[0] for arg in node.args]
                return f"token_list_get(&{args[0]}, {args[1]})", "Token"
            if name not in self.defined_functions:
                # try qualified match fallback
                for fn in self.defined_functions:
                    if fn.endswith(f"_{name}"):
                        print(f"[INFO] Resolved '{name}' → '{fn}'")
                        name = fn
                        break
                # Handle extern function calls with special argument casting
            if name in self.externs:
                arg_codes = []
                for i, arg in enumerate(node.args):
                    arg_code, _ = self.gen_expr(arg)

                    # Smart cast for C functions expecting struct sockaddr*
                    if name in ("bind", "connect", "accept") and i == 1:
                        arg_code = f"(struct sockaddr*){arg_code}"
                   
                    arg_codes.append(arg_code)
                ret_type_key = self.function_types.get(name, "int")
                print(f"[DEBUG] Extern call to {name}, return type = {ret_type_key}")
                return f"{name}({', '.join(arg_codes)})", ret_type_key

            # --- Struct instantiation ---
            if name in self.struct_defs:
                struct_def = self.struct_defs[name]
                tmp = self.new_temp()
                arg_exprs = [self.gen_expr(arg)[0] for arg in node.args]

                if len(arg_exprs) != len(struct_def.fields):
                    raise Exception(f"Struct {name} expects {len(struct_def.fields)} fields, got {len(arg_exprs)}")

                assigns = [
                    f"{tmp}.{field_name} = {val};"
                    for (field_name, _), val in zip(struct_def.fields, arg_exprs)
                ]
                self.body_lines.append(f"{name} {tmp};\n" + "\n".join(assigns))
                return tmp, name
           
            if name == "string":
                if not node.args:
                    raise Exception("string() requires 1 argument")

                value_code, value_type = self.gen_expr(node.args[0])
                tmp = self.new_temp()
                self.body_lines.append(f"char {tmp}[128];")

                format_spec = "%s"
                if value_type in ("int", "number", "bool"):
                    format_spec = "%d"
                elif value_type == "float":
                    format_spec = "%f"

                self.body_lines.append(f'snprintf({tmp}, sizeof({tmp}), "{format_spec}", {value_code});')
                return tmp, "string"

            # --- Built-in: len(...) ---
            if name == "len":
                arg_expr, arg_type = self.gen_expr(node.args[0])
                print(f"[DEBUG] len() called with arg_expr = {arg_expr}, arg_type = {arg_type}")
                if self.normalize_type(arg_type) == "list":
                    return f"{arg_expr}.size", "int"
                elif self.normalize_type(arg_type) == "array":
                    return f"sizeof({arg_expr}) / sizeof({arg_expr}[0])", "int"
                elif self.normalize_type(arg_type) == "string":
                    return f"strlen({arg_expr})", "int"
                elif self.normalize_type(arg_type) == "int":
                    # Define behavior for integers
                    return "1", "int"  # Treat an integer as a single element
                else:
                    raise Exception("len() only supported for lists, arrays, and strings")

            # --- Built-in: number(...) ---
            if name == "number":
                value_code, value_type = self.gen_expr(node.args[0])
                if value_type in ("int", "bool"):
                    return value_code, "int"

                tmp = self.new_temp()
                end = self.new_temp()  

                check_code = f"""
                char* {end};
                int {tmp} = strtol({value_code}, &{end}, 10);
                if (*{end} != '\\0') {{
                    raise("Cannot convert to number");
                }}
                """.strip()

                self.body_lines.extend(check_code.splitlines())
                return tmp, "int"
            if name == "float":
                value_code, _ = self.gen_expr(node.args[0])
                return f"((float){value_code})", "float"
            
            if name == "int":
                value_code, _ = self.gen_expr(node.args[0])
                return f"((int){value_code})", "int"

            # --- Built-in: input(...) ---
            if name == "input":
                tmp = self.new_temp()
                buf = f"{tmp}_buf"

                if node.args:
                    prompt_code, _ = self.gen_expr(node.args[0])
                    self.body_lines.extend([
                        f"char {buf}[1024];",
                        f'printf("%s", {prompt_code});',
                        f"fgets({buf}, sizeof({buf}), stdin);",
                        f"{buf}[strcspn({buf}, \"\\n\")] = 0;"
                    ])
                else:
                    self.body_lines.extend([
                        f"char {buf}[1024];",
                        f"fgets({buf}, sizeof({buf}), stdin);",
                        f"{buf}[strcspn({buf}, \"\\n\")] = 0;"
                    ])

                # NEW — depending on context type hint
                expected_type = getattr(node, "_expected_type", None)

                if expected_type == "float":
                    return f"atof({buf})", "float"
                elif expected_type == "int":
                    return f"atoi({buf})", "int"
                else:
                    return f"strdup({buf})", "string"


            # --- Built-in: print(...) ---
            if name == "print":
                print(node.args)
                args = [self.gen_expr(arg) for arg in node.args]
                if any(not isinstance(a, tuple) or len(a) != 2 for a in args):
                    raise Exception(f"[ERROR] Malformed function args: {args}")

                fmt_parts = []
                arg_exprs = []

                for code, arg_type in args:
                    print("[DEBUG] print arg type:",args, arg_type)                    
                    if arg_type == "list":
                        tmp_buf = self.new_temp()
                        if not code.isidentifier():
                            tmp_list = self.new_temp()
                            self.body_lines.append(f"List {tmp_list} = {code};")
                            code = tmp_list
                        self.body_lines.append(f"char {tmp_buf}[256];")
                        self.body_lines.append(f"list_to_string(&{code}, {tmp_buf}, sizeof({tmp_buf}));")
                        code = tmp_buf
                        fmt_parts.append("%s")

                    elif arg_type == "string":
                        fmt_parts.append("%s")
                    elif arg_type == "int":
                        fmt_parts.append("%d")
                    elif arg_type == "bool":
                        fmt_parts.append("%s")
                        code = f"({code} ? \"true\" : \"false\")"
                    elif arg_type == "float":
                        fmt_parts.append("%f")
                    # elif arg_type == "list":
                    #     self.body_lines.append(f"list_to_string({code});")
                    else:
                        fmt_parts.append("%s")
                    arg_exprs.append(code)

                fmt_str = " ".join(fmt_parts) + "\\n"
                self.body_lines.append(f'printf("{fmt_str}", {", ".join(arg_exprs)});')
                return "", "void"

            # --- Built-in: write(...) / addto(...) ---
            if name in ("write", "addto"):
                filename_arg = self.gen_expr(node.args[0])[0]
                content_arg = self.gen_expr(node.args[1])[0]
                spacing_arg = self.gen_expr(node.args[2])[0]
                mode = '"w"' if name == "write" else '"a"'

                tpl = env.get_template("write_file.c.j2")
                rendered = tpl.render(
                    filename=filename_arg,
                    content=content_arg,
                    mode=mode,
                    spacing=spacing_arg,
                )
                self.body_lines.append(rendered)
                return "0", "int"
            if name == "printp":
                if len(node.args) < 2:
                    prec_code = 6
                else: 
                    prec_code, _ = self.gen_expr(node.args[1])
                val_code, val_type = self.gen_expr(node.args[0])
                fmt_buf = self.new_temp()
                self.body_lines.append(f"char {fmt_buf}[10];")
                self.body_lines.append(f'snprintf({fmt_buf}, sizeof({fmt_buf}), "%%.%df\\n", {prec_code});')
                self.body_lines.append(f'printf({fmt_buf}, {val_code});')
                return "", "void"

            if name == "rf" or name == "random_float":
                if len(node.args) == 2:
                    low_code, _ = self.gen_expr(node.args[0])
                    high_code, _ = self.gen_expr(node.args[1])
                    tmp = self.new_temp()
                    self.body_lines.append(
                        f"double {tmp} = ((double)rand() / RAND_MAX) * ({high_code} - {low_code}) + {low_code};"
                    )
                    return tmp, "float"
                elif len(node.args) == 0:
                    tmp = self.new_temp()
                    self.body_lines.append(
                        f"double {tmp} = (double)rand() / RAND_MAX;"
                    )
                    return tmp, "float"
                else:
                    raise Exception(f"rf() expects 0 or 2 arguments, got {len(node.args)}")
            if name == "int":
                value_code, value_type = self.gen_expr(node.args[0])
                if value_type == "float":
                    return f"(int)({value_code})", "int"
                return value_code, "int"


            if name == "ri" or name == "random_int":
                if len(node.args) != 2:
                    raise Exception(f"{name} requires 2 arguments")
                low_code, _ = self.gen_expr(node.args[0])
                high_code, _ = self.gen_expr(node.args[1])
                tmp = self.new_temp()
                self.body_lines.append(f"int {tmp} = rand() % ({high_code} - {low_code} + 1) + {low_code};")
                return tmp, "int"



            # --- Built-in: read(...) ---
            if name == "read":
                filename_code, _ = self.gen_expr(node.args[0])
                tmp = self.new_temp()
                tpl = env.get_template("read_file.c.j2")
                rendered = tpl.render(tmp=tmp, filename=filename_code)
                self.body_lines.append(rendered)
                return tmp, "string"

            # --- User-defined function ---
            func_name = self.sanitize_name(name)
            args = [self.gen_expr(arg) for arg in node.args]
            if func_name in self.function_types:
                return_type = self.function_types[func_name]
                return f"{func_name}({', '.join(arg_code for arg_code, _ in args)})", return_type
           
            if name in self.defined_functions:
                arg_codes = [arg_code for arg_code, _ in args]
                return f"{name}({', '.join(arg_codes)})", "void"

            

            # Check for unqualified calls and try to match them to qualified ones
            if name not in self.defined_functions:
                print(f"[WARN] {name} not in {self.defined_functions}")

                # Attempt to resolve fully-qualified function name
                matches = [fn for fn in self.defined_functions if fn.endswith(f"_{name}")]
                if matches:
                    name = matches[0]  # Use the qualified match
                    print(f"[INFO] Resolved call '{name}' via suffix match.")
                else:
                    raise Exception(f"Unknown function: {name}")

            print(f"[DEBUG] Attempting to call: {name}")
            print(f"[DEBUG] Known functions: {self.defined_functions}")

            # Fallback if function has no return (void)
            return f"{name}({', '.join(arg_code for arg_code, _ in args)})", "void"

# Final fallback — this runs *only* if node.func wasn't an Identifier
        print(f"[ERROR] Unknown call expression structure: {type(node.func).__name__} - {repr(node.func)}")
        raise Exception("Unsupported call expression structure or missing name.")


    def get_expr_type(self, expr):

        if isinstance(expr, Identifier):
            return self.get_type(expr.name)

        elif isinstance(expr, MemberAccess):
            obj_type = self.get_expr_type(expr.obj)
            if obj_type in self.struct_defs:
                for field, typ in self.struct_defs[obj_type].fields:
                    if field == expr.name:
                        return typ
            raise Exception(f"Unknown field {expr.name} in {obj_type}")

        elif isinstance(expr, SubscriptExpr):
            container_type = self.get_expr_type(expr.target)
            if container_type == "list":
                return "int"  # or "string" if you tracked list types
            if container_type == "string":
                return "char"
            return None

        return None  # fallback




    def gen_Assignment(self, node):
        # Handle: x = 42
        if isinstance(node.target, str):
            lhs = node.target
            rhs_code, _ = self.gen_expr(node.expr)
            self.body_lines.append(f"{lhs} = {rhs_code};")

        # Handle: x = 42 (Identifier node)
        elif isinstance(node.target, Identifier):
            lhs = node.target.name
            rhs_code, _ = self.gen_expr(node.expr)
            self.body_lines.append(f"{lhs} = {rhs_code};")

        # Handle: user.name = "John"
        elif isinstance(node.target, MemberAccess):
            obj_code, obj_type = self.gen_expr(node.target.obj)
            field_name = node.target.name
            rhs_code, _ = self.gen_expr(node.expr)

            if obj_type.startswith("*") or obj_type.startswith("&"):
                self.body_lines.append(f"{obj_code}->{field_name} = {rhs_code};")
            else:
                self.body_lines.append(f"{obj_code}.{field_name} = {rhs_code};")


        # Handle: myList[0] = 99
        elif isinstance(node.target, SubscriptExpr):
            target_code, target_type = self.gen_expr(node.target.target)
            index_code, _ = self.gen_expr(node.target.index)
            rhs_code, _ = self.gen_expr(node.expr)
            if target_type == "list":
                self.body_lines.append(f"{target_code}.items[{index_code}] = {rhs_code};")
            elif target_type == "array":
                self.body_lines.append(f"{target_code}[{index_code}] = {rhs_code};")
            else:
                raise Exception(f"Cannot assign to subscript of {target_type}")

        else:
            raise NotImplementedError("Unsupported assignment target")

    def gen_ReturnStatement(self, node):
        value_code, actual_type = self.gen_expr(node.expr)
        declared_type = getattr(node, "_force_return_type", None)

        if declared_type and declared_type != actual_type:
            if declared_type == "float" and actual_type == "int":
                value_code = f"(float)({value_code})"
            elif declared_type == "int" and actual_type == "float":
                value_code = f"(int)({value_code})"
        self.body_lines.append(f"return {value_code};")

    def map_type(self, forge_type):
        if forge_type.startswith("&"):
            inner = forge_type[1:]
            c_type = self.map_type(inner)
            print(f"[DEBUG] map_type({forge_type}) → {c_type}*")
            return f"{c_type}*"

        if forge_type in self.struct_defs:
            return forge_type
        if forge_type in ("int", "number"):
            print(f"[DEBUG] map_type({forge_type}) → int")
            return "int"
        if forge_type == "float":
            print(f"[DEBUG] map_type({forge_type}) → double")
            return "double"
        if forge_type in ("str", "string"):
            print(f"[DEBUG] map_type({forge_type}) → char*")
            return "char*"
        if forge_type == "bool":
            print(f"[DEBUG] map_type({forge_type}) → int")
            return "int"
        if forge_type == "pointer":      
            print(f"[DEBUG] map_type({forge_type}) → intptr_t")
            return "void*"
        if forge_type == "address" or forge_type == "handle":
            return "intptr_t"
        if forge_type == "list":
            print(f"[DEBUG] map_type({forge_type}) → List")
            return "List"
        if forge_type == "arr":
            print(f"[DEBUG] map_type({forge_type}) → Array*")
            return "Array*"
        if forge_type == "array_value":
            print(f"[DEBUG] map_type({forge_type}) → Array")
            return "Array"
        if forge_type == "StringList":
            return "StringList"
        if forge_type == "TokenList":
            return "TokenList"
        if forge_type == "Token" or forge_type == "token":
            return "Token"
            print("DEBUG: Setting", forge_type, " to Token")
        if forge_type == "Tokens" or forge_type == "tokens":
            return "TokenList"
        
        if forge_type == "Node":
            return "Node"  
        
        print(f"[DEBUG] map_type({forge_type}) → int [fallback]")
        return "int"

        



    def normalize_type(self, t):
        if t == "str":
            return "string"
        if t == "FToken":
            return "Token"
        return t




    def gen_FunctionDef(self, node):
        name = self.sanitize_name(node.name)
        sanitized = self.sanitize_name(name)
        self.defined_functions.add(sanitized)
        
    
        self.push_scope()  # Begin function scope
        # use declared return type first

        if node.return_type:
            declared_ret = node.return_type
            return_type_inferred = declared_ret  # ⬅️ override inferred
            self.function_types[sanitized] = declared_ret
            return_type = self.map_type(declared_ret)
            print(f"[DEBUG] function_types['{name}'] (declared override) = {declared_ret}")

            if sanitized not in self.function_types:
                self.function_types[sanitized] = declared_ret
                print(f"[DEBUG] function_types['{name}'] (declared) = {declared_ret}")
        else:
            return_type = "void"

        param_decls = []

        for param_name, type_hint in node.params:
            # Default to "int" if no type hint
            if type_hint:
                inferred_type = type_hint
            elif node.return_type == "float":
                inferred_type = "float"  # if return is float, assume params should be too
            else:
                inferred_type = "int"
            
            
            # Apply heuristic overrides based on function name or usage
            if node.name in {"maxa", "mina"}:
                inferred_type = "array"
                self.set_type(param_name, inferred_type)
            
            # Re-infer type based on usage if needed
            current_type = self.get_type(param_name)
            if current_type == "int" and param_name in str(node.body):
                if f"{param_name}[" in str(node.body) or f"{param_name}.items" in str(node.body):
                    print(f"[INFO] Overriding '{param_name}' as 'list' due to indexing pattern")
                    inferred_type = "list"
                    self.set_type(param_name, inferred_type)

            # Set variable in scope
            self.declare_var(param_name, inferred_type)
            self.scope_stack[-1][param_name] = inferred_type
            self.set_type(param_name, inferred_type)
            



            # Final C type mapping
            if inferred_type == "array":
                c_type = "Array*"
            elif inferred_type == "list":
                c_type = "List"
            elif inferred_type == "string":
                c_type = "char*"
            else:
                c_type = self.map_type(inferred_type)

            param_decls.append(f"{c_type} {param_name}")
        
        # Infer return type
        ret_expr = None
        # Respect explicit return type annotation
        # ✅ Use declared return type if available
        if node.return_type:
            return_type_inferred = node.return_type
        elif ret_expr:
            _, return_type_inferred = self.gen_expr(ret_expr)
        else:
            return_type_inferred = "void"


        if node.body and not hasattr(node.body, 'statements'):
            ret_expr = node.body
        elif hasattr(node.body, 'statements'):
            for stmt in reversed(node.body.statements):
                if isinstance(stmt, ReturnStatement):
                    ret_expr = stmt.expr
                    break

        if ret_expr:
            
            _, return_type_inferred = self.gen_expr(ret_expr)
            # if isinstance(ret_expr, ListLiteral) or 'add(' in expr_code or '->data' in expr_code:
            #     return_type_inferred = "list"
            # Force float if .5 math involved
            if isinstance(ret_expr, BinaryExpr):
                for side in [ret_expr.left, ret_expr.right]:
                    if isinstance(side, NumberLiteral) and isinstance(side.value, float):
                        return_type_inferred = "float"

            return_type = self.map_type(return_type_inferred)

            if return_type == "function":
                return_type = "int"
            # Ensure known return type
            if return_type_inferred == "number":
                return_type_inferred = "int"
            return_type = self.map_type(return_type_inferred)
            # Do not overwrite if already set (e.g., by ExternExpr)
            if sanitized not in self.function_types:
                self.function_types[sanitized] = return_type_inferred
                print(f"[DEBUG] function_types['{name}'] = {self.function_types[name]}")
            else:
                print(f"[INFO] Skipped overwrite of function_types['{name}'] = {return_type_inferred} (already set to {self.function_types[sanitized]})")

            print(f"[DEBUG] function_types['{name}'] = {self.function_types[name]}")
        else:
            return_type = "void"

        # Transpile body
        if node.body and not hasattr(node.body, 'statements'):
            
            
            expr_code, _ = self.gen_expr(node.body)
            body = f"return {expr_code};"
        else:
            for stmt in node.body.statements:
                if isinstance(stmt, ReturnStatement):
                    stmt._force_return_type = node.return_type
            body = self.transpile_block(node.body)
        

        self.pop_scope()  # Exit function scope

        tpl = env.get_template("function_def.c.j2")
        return_type = self.map_type(self.function_types.get(sanitized, return_type_inferred))
        print(f"[RENDER] Emitting function {sanitized} with return type: {return_type}")
        code = tpl.render(name=sanitized, return_type=return_type, params=param_decls, body=body)
        self.functions.append(code)
        print(f"[DEBUG] function_types['{sanitized}'] = {self.function_types.get(sanitized, 'NOT SET')}")






    def indent(self, code, spaces=4):
        return "\n".join(" " * spaces + line if line.strip() else "" for line in code.splitlines())


    def gen_AttemptRescue(self, node):
        try_code = self.transpile_block(node.try_block)
        rescue_code = self.transpile_block(node.rescue_block)
        rescue_name = node.error_name

        rendered = f"""
    if (!setjmp(__context.env)) {{
    {self.indent(try_code)}
    }} else {{
        const char* {rescue_name} = __context.error;
    {self.indent(rescue_code)}
    }}
    """.strip()

        self.body_lines.append(rendered)

    def gen_LoadStmt(self, node: LoadStmt):
        # Strip quotes from "math.forge"
        path = node.path.strip('"')

        if not path.endswith(".forge"):
            raise Exception(f"Only .forge files supported, got: {path}")

        if path in self.loaded_modules:
            return
        self.loaded_modules.add(path)

        full_path = None
        for base in self.module_search_paths:
            candidate = os.path.join(base, path)
            if os.path.exists(candidate):
                full_path = candidate
                break

        if not full_path:
            raise FileNotFoundError(f"Cannot find module file: {path}")

        with open(full_path, "r") as f:  # use full_path
            source_code = f.read()

        tokens = Lexer(source_code).tokenize()
        ast = Parser(tokens).parse()

        module_name = os.path.splitext(os.path.basename(full_path))[0]  # from full_path

        # First pass: Register all functions
        for stmt in ast.statements:
            if isinstance(stmt, FunctionDef):
                fn_name = self.sanitize_name(stmt.name)

                if not fn_name.startswith(module_name + "_"):
                    qualified_name = f"{module_name}_{fn_name}"
                    stmt.name = qualified_name
                else:
                    qualified_name = fn_name

                self.defined_functions.add(qualified_name)

                if stmt.return_type:
                    self.function_types[qualified_name] = stmt.return_type
                    print(f"[DEBUG] Loaded function {qualified_name} with declared return: {stmt.return_type}")

                    if fn_name not in self.function_types:
                        self.function_types[fn_name] = stmt.return_type
                        self.defined_functions.add(fn_name)
                        print(f"[DEBUG] Aliased {fn_name} → {qualified_name}")
                elif stmt.body and hasattr(stmt.body, "statements"):
                    for s in reversed(stmt.body.statements):
                        if isinstance(s, ReturnStatement):
                            _, typ = self.gen_expr(s.expr)
                            self.function_types[qualified_name] = typ
                            print(f"[DEBUG] Inferred return type for {qualified_name}: {typ}")
                            break

        # Second pass: Transpile functions (now all are registered)
        for stmt in ast.statements:
            self.transpile(stmt)





    def transpile_block(self, block_node):
        saved_lines = self.body_lines
        self.body_lines = []
        for stmt in block_node.statements:
            self.transpile(stmt)
        result = "\n".join(self.body_lines)
        self.body_lines = saved_lines
        return result
    
    def map_binary_op(self, op):
        table = {
            "PLUS": "+",
            "MINUS": "-",
            "MUL": "*",
            "DIV": "/",
            "MOD": "%",
            "EQEQ": "==",
            "NEQ": "!=",
            "LT": "<",
            "LTE": "<=",
            "GT": ">",
            "GTE": ">=",
            "AND": "&&",
            "OR": "||",
            "PLUSPLUS": "++",
            "MINUSMINUS": "--",
            "POW": "^",
        }
        return table.get(op, op)



    def gen_expr(self, expr):
        #print("[DEBUG] gen_expr type:", type(expr).__name__)
        if isinstance(expr, NumberLiteral):
            typ = "float" if expr.is_float else "int"
            return str(expr.value), typ
        
        elif isinstance(expr, AddressOf):
            inner_code, inner_type = self.gen_expr(expr.expr)
            return f"&{inner_code}", f"*{inner_type}"


        elif isinstance(expr, StringLiteral):
            escaped = escape_c_string(expr.value)
            return f"\"{escaped}\"", "string"
        
        elif isinstance(expr, ExternExpr):
            print(f"[DEBUG] REGISTERING extern {expr.name}")
            self.externs[expr.name] = expr.arg_types
            self.defined_functions.add(expr.name)
            existing_type = self.function_types.get(expr.name)
            new_type = expr.return_type or "int"

            # Only overwrite if it's not already set, or if the new one is more specific
            if existing_type is None or (existing_type == "int" and new_type != "int"):
                self.function_types[expr.name] = new_type
                print(f"[DEBUG] Set function_types['{expr.name}'] = {new_type}")
            else:
                print(f"[INFO] Skipped overwrite of function_types['{expr.name}'] = {new_type}")

            return "", "extern"


        
        elif isinstance(expr, MemberAccess):
            obj_code, obj_type = self.gen_expr(expr.obj)
            if obj_type == "Token" and expr.name == "value":
                return f"{obj_code}.value", "string"

            # Check if obj_type is a known struct
            if obj_type in self.struct_defs:
                struct_def = self.struct_defs[obj_type]
                field_type = None
                for field_name, f_type in struct_def.fields:
                    if field_name == expr.name:
                        field_type = f_type
                        break
                if field_type is None:
                    raise Exception(f"Unknown field {expr.name} in struct {obj_type}")
                if obj_type.startswith("*") or obj_type.startswith("&"):
                    return f"{obj_code}->{expr.name}", field_type
                else:
                    return f"{obj_code}.{expr.name}", field_type
            
            if obj_type.startswith("*") or obj_type.startswith("&"):
                return f"{obj_code}->{expr.name}", "int"
            else:
                return f"{obj_code}.{expr.name}", "int"
            



        elif isinstance(expr, Identifier):
            var_name = expr.name
            var_type = self.get_type(var_name) or "int"  # default fallback
            return var_name, var_type
        
        elif isinstance(expr, NullLiteral):
            return "-1", "int"


        elif isinstance(expr, BinaryExpr):
            op = self.map_binary_op(expr.op)
            left_code, left_type = self.gen_expr(expr.left)
            right_code, right_type = self.gen_expr(expr.right)
            
            # Special case: string equality even if types weren't inferred
            if op in ("==", "!="):
                if (
                    left_type == "string"
                    or right_type == "string"
                    or isinstance(expr.left, StringLiteral)
                    or isinstance(expr.right, StringLiteral)
                ):
                    cmp = "!=" if op == "!=" else "=="
                    return f"(strcmp({left_code}, {right_code}) {cmp} 0)", "bool"



            # Handle string concatenation
            if op == "+" and ("string" in (left_type, right_type)):
                # Ensure both operands are strings
                if left_type != "string":
                    left_tmp = self.new_temp()
                    fmt = "%s" if left_type == "char*" else "%d"
                    self.body_lines.append(f"char {left_tmp}[32];")
                    self.body_lines.append(f'snprintf({left_tmp}, sizeof({left_tmp}), "{fmt}", {left_code});')
                    left_code = left_tmp

                if right_type != "string":
                    print("Right is not string")
                    right_tmp = self.new_temp()
                    fmt = "%s" if right_type == "char*" else "%d"
                    self.body_lines.append(f"char {right_tmp}[32];")
                    self.body_lines.append(f'snprintf({right_tmp}, sizeof({right_tmp}), "{fmt}", {right_code});')
                    right_code = right_tmp



                result_tmp = self.new_temp()
                self.body_lines.append(f"char {result_tmp}[1024];")
                self.body_lines.append(f'snprintf({result_tmp}, sizeof({result_tmp}), "%s%s", {left_code}, {right_code});')
                tmp_heap = self.new_temp("heapstr")
                self.body_lines.append(f"char* {tmp_heap} = strdup({result_tmp});")  # ✅ allocate on heap
                return tmp_heap, "string"


            # Normal numeric ops
            result_code = f"({left_code} {op} {right_code})"
            if left_type == "float" or right_type == "float":
                left_code = f"(float){left_code}" if left_type != "float" else left_code
                right_code = f"(float){right_code}" if right_type != "float" else right_code
                result_code = f"({left_code} {op} {right_code})"
                return result_code, "float"
            else:
                result_code = f"({left_code} {op} {right_code})"
                return result_code, "int"



        elif isinstance(expr, ListLiteral):
            if hasattr(expr, '_forced_type_hint') and expr._forced_type_hint:
                if expr._forced_type_hint == "StringList":
                    list_type = "StringList"
                    create_func = "string_list_create"
                    add_func = "string_list_add"
                    result_type = "StringList"
                else:
                    list_type = "List"
                    create_func = "list_create"
                    add_func = "list_add"
                    result_type = "list"
            else:
                # Fallback: detect based on elements
                if not expr.elements:
                    return "list_create()", "list"
                
                is_string_list = all(isinstance(el, StringLiteral) for el in expr.elements)

                if is_string_list:
                    list_type = "StringList"
                    create_func = "string_list_create"
                    add_func = "string_list_add"
                    result_type = "stringlist"
                else:
                    list_type = "List"
                    create_func = "list_create"
                    add_func = "list_add"
                    result_type = "list"

            temp_name = self.new_temp()
            self.body_lines.append(f"{list_type} {temp_name} = {create_func}();")

            for el in expr.elements:
                el_code, _ = self.gen_expr(el)
                self.body_lines.append(f"{add_func}(&{temp_name}, {el_code});")

            return temp_name, result_type



        elif isinstance(expr, SubscriptExpr):
            target_type = self.get_expr_type(expr.target)
            target_code, _ = self.gen_expr(expr.target)
            index_code, _ = self.gen_expr(expr.index)

            is_value = (
                isinstance(expr.target, Identifier)
                and self.get_type(expr.target.name) == "array_value"
            )
            if self.normalize_type(target_type) in {"array", "array_value"}:
                if is_value:
                    target_code = f"&{target_code}"
                return f"*(int*)array_get({target_code}, {index_code})", "int"

            
            print(f"[DEBUG] Subscript target: {target_code}, Type: {target_type}, Index: {index_code}")

            if self.normalize_type(target_type) == "list":
                if self.get_type(target_code) == "string":
                    return f"list_get_str(&{target_code}, {index_code})", "string"
                return f"{target_code}.items[{index_code}]", "int"
            
            elif self.normalize_type(target_type) == "StringList":
                return f"{target_code}.items[{index_code}]", "string"
            elif self.normalize_type(target_type) == "TokenList" :
                return f"token_list_get(&{target_code}, {index_code})", "Token"



            elif self.normalize_type(target_type) in {"array", "array_value"}:
                # Check if the target is a value (declared as Array) vs a pointer (Array*)
                is_value = (
                    isinstance(expr.target, Identifier)
                    and self.get_type(expr.target.name) == "array_value"
                )
                if is_value:
                    target_code = f"&{target_code}"
                return f"*(int*)array_get({target_code}, {index_code})", "int"


            elif self.normalize_type(target_type) == "string":
                tmp = self.new_temp()
                self.body_lines.append(f"char {tmp} = {target_code}[{index_code}];")
                return tmp, "char"

            else:
                if isinstance(expr.target, Identifier):
                    name = expr.target.name
                    current_type = self.get_type(name)
                    if not current_type or current_type == "int":
                        print(f"[INFO] Inferring '{name}' as 'array' due to subscript")
                        self.declare_var(name, "array")
                        return f"*(int*)array_get({target_code}, {index_code})", "int"

                raise Exception(f"Cannot subscript non-list/array: {target_type}")


        elif isinstance(expr, UnaryExpr):
            operand_code, _ = self.gen_expr(expr.operand)

            if expr.op == "-":
                return f"-({operand_code})", "int"
            elif expr.op == "!":
                return f"!({operand_code})", "bool"
            else:
                raise Exception(f"Unsupported unary operator: {expr.op}")
            
        elif isinstance(expr, ArrayLiteral):
            if not expr.elements:
                raise Exception("Cannot infer type for empty array")

            # Generate all elements
            element_exprs = []
            temp_vars = []
            for i, el in enumerate(expr.elements):
                code, el_type = self.gen_expr(el)
                temp_var = self.new_temp()
                temp_vars.append(temp_var)
                if 'func_name' in locals():
                    print(f"[DEBUG] func_name = {func_name}")
                    print(f"[DEBUG] function_types.get(func_name) = {self.function_types.get(func_name)}")
                    ret_type = self.function_types.get(func_name, "int")
                else:
                    print(f"[DEBUG] Inferred element type: {el_type}")
                    ret_type = el_type

                self.body_lines.append(f"{ret_type} {temp_var} = {code};")
                element_exprs.append(temp_var)

            # Infer type from the first element
            first_code, first_type = self.gen_expr(expr.elements[0])
            array_type = self.map_type(first_type)

            temp_array = self.new_temp()
            array_init = f"Array {temp_array} = array_create(sizeof({array_type}), {len(element_exprs)});"

            self.body_lines.append(array_init)

            # Populate the array
            for i, temp_var in enumerate(temp_vars):
                self.body_lines.append(f"array_set(&{temp_array}, {i}, &{temp_var});")

            return temp_array, "array_value"
        

        elif isinstance(expr, AttemptRescueExpr):
            expr_key = id(expr)
            if not hasattr(self, "_attempt_expr_cache"):
                self._attempt_expr_cache = {}

            if expr_key in self._attempt_expr_cache:
                return self._attempt_expr_cache[expr_key], "int"

            result_var = self.new_temp("attempt_result")
            guard_var = self.new_temp("attempt_guard")
            exit_label = self.new_temp("attempt_exit")

            self._attempt_expr_cache[expr_key] = result_var

            # Declare result early
            self.body_lines.append(f"int {result_var};")
            self.body_lines.append(f"static int {guard_var} = 0;")
            self.body_lines.append(f"if (!{guard_var}) {{")
            self.indent_level += 1
            self.body_lines.append(f"{guard_var} = 1;")
            self.body_lines.append(f"if (!setjmp(__context.env)) {{")
            self.indent_level += 1

            saved_lines = self.code
            self.code = []
            try_expr_code, _ = self.gen_expr(expr.try_expr)
            try_block = self.code
            self.code = saved_lines
            self.body_lines.extend(try_block)
            self.body_lines.append(f"{result_var} = {try_expr_code};")
            self.body_lines.append(f"goto {exit_label};")

            self.indent_level -= 1
            self.body_lines.append("} else {")
            self.indent_level += 1

            saved_lines = self.code
            self.code = []
            rescue_expr_code, _ = self.gen_expr(expr.rescue_expr)
            rescue_block = self.code
            self.code = saved_lines
            self.body_lines.extend(rescue_block)
            self.body_lines.append(f"{result_var} = {rescue_expr_code};")
            self.body_lines.append(f"goto {exit_label};")

            self.indent_level -= 1
            self.body_lines.append("}")
            self.indent_level -= 1
            self.body_lines.append("}")
            self.body_lines.append(f"{exit_label}:;")

            return result_var, "int"




        elif isinstance(expr, StructInstance):
            struct_name = expr.struct_name
            tmp = self.new_temp()

            field_values = [self.gen_expr(arg)[0] for arg in expr.args]

            # Skip needing struct_def.fields — hardcode fields in order for now
            # You could make a fallback if you're not storing struct_defs
            assignments = []
            for i, val_code in enumerate(field_values):
                assignments.append(f"{tmp}.field{i} = {val_code};")  # temp fallback if you don’t track fields

            self.body_lines.append(f"{struct_name} {tmp};")
            self.body_lines.extend(assignments)

            return tmp, struct_name



        elif isinstance(expr, CallExpr):
            return self.gen_CallExpr(expr)  # DELEGATE HERE
        
        elif isinstance(expr, PropertyAccess):
            obj_code, obj_type = self.gen_expr(expr.object)
            prop = expr.prop

            # Try to resolve from struct fields
            struct_def = self.struct_defs.get(obj_type)
            if struct_def:
                for field_name, field_type in struct_def.fields:
                    if field_name == prop:
                        return f"{obj_code}.{prop}", field_type

            # Fallback: return as unknown
            print(f"[WARN] Could not resolve property type: {obj_type}.{prop}")
            return f"{obj_code}.{prop}", "unknown"
        # optionally resolve actual type later

        


        else:
            raise NotImplementedError(f"Unsupported expression type: {type(expr).__name__}")


    def gen_ExpressionStatement(self, node):
        if isinstance(node.expr, Assignment):
            self.transpile(node.expr)
        else:
            inner_expr = node.expr
            if isinstance(inner_expr, ExpressionStatement):
                inner_expr = inner_expr.expr  # Unwrap nested

            expr_code, _ = self.gen_expr(inner_expr)

            self.body_lines.append(f"{expr_code};")


    # def map_op(self, op):
    #     return {
    #         "PLUS": "+", "MINUS": "-", "MUL": "*", "DIV": "/", "MOD": "%",
    #         "EQEQ": "==", "NEQ": "!=", "LT": "<", "GT": ">", "LTE": "<=", "GTE": ">=",
    #     }.get(op, op)



# Entry point
def main():
    if len(sys.argv) != 2:
        print("Usage: python transpile_to_c.py <source.forge>")
        return

    filename = sys.argv[1]
    with open(filename) as f:
        source = f.read()

    # Transpile
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    transpiler = CTranspiler()
    c_code = transpiler.gen_Program(ast)

    # Write output.c
    with open("output.c", "w") as out:
        out.write(c_code)
        print("Transpiled to output.c")

    # Compile with gcc
    executable = "output.exe" if platform.system() == "Windows" else "./output"
    compile_cmd = ["gcc", "-Iincludes", "output.c", "-o", "output"]


    try:
        subprocess.run(compile_cmd, check=True)
        print("Compiled to 'output'")
    except subprocess.CalledProcessError:
        print("Compilation failed")
        return

    # Run the output program
    print("Running program:")
    subprocess.run([executable])

if __name__ == "__main__":
    main()
