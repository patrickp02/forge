# Forge Language

Forge is a statically-typed, high-level programming language that transpiles into C. It is designed for building performant low-level systems using a high-level ergonomic syntax inspired by modern scripting languages. 

## Features

- Clean and expressive syntax for defining variables, functions, structs, and control flow
- Static typing with type inference and optional annotations
- High-level constructs like `let`, `if/else`, `for`, `while`, and `match'
- Struct support with dot access and field mutation
- Modules and imports (`load`)
- Runtime helpers for file I/O, hashing, random numbers, lists, arrays, and more
- Built-in functions: `print`, `input`, `read`, `write`, `addto`, `len`, `number`, `string`, `hash`, `rf`, `ri`
- Support for inline expressions
- Supports manual memory allocation (Currently, Forge does not have a set garbage collection system so all memory must be freed manually to prevent leaks. This will hopefully be changed in the future.)

## Architecture

Forge includes the following components:

- `lexer.py`: Tokenizes the Forge source code into a stream of tokens
- `forge_parser.py`: (not included here) Parses tokens into an abstract syntax tree (AST)
- `interpreter.py`: Walks the AST and executes code directly (for development or REPL usage)
- `transpile_to_c.py`: Translates AST into equivalent C code, handling type mapping, scoping, and templated C generation using Jinja2
- `templates/`: Jinja2 templates used to render C code for functions, statements, and built-ins

## Example

Forge code:
```forge
fn test_bind() {
    let sock = socket(2, 1, 0)  # AF_INET, SOCK_STREAM, 0
    print("Socket FD:", sock)

    let port = htons(8080)
    print("Port (network order):", port)

    let addr = make_sockaddr(port)
    let res = bind(sock, addr, 16)
    print("bind() result:", res)

    let res2 = listen(sock, 5)
    print("listen() result:", res2)

    close(sock)
    print("Socket closed.")
}

test_bind()
```
## Transpiled C code:

```c
int net_socket_tcp() {
return socket(2, 1, 0);
}
int net_close_socket(intptr_t s) {
close(s);
}
int net_create() {
int s = socket(2, 1, 0);
}
int test_bind() {
int sock = socket(2, 1, 0);
    printf("%s %d\n", "Socket FD:", sock);
    ;
    int port = htons(8080);
    printf("%s %d\n", "Port (network order):", port);
    ;
    intptr_t addr = make_sockaddr(port);
    int res = bind(sock, (struct sockaddr*)addr, 16);
    printf("%s %d\n", "bind() result:", res);
    ;
    int res2 = listen(sock, 5);
    printf("%s %d\n", "listen() result:", res2);
    ;
    close(sock);
    printf("%s\n", "Socket closed.");
    ;
}



int main() {

    net_create();
    ;
    test_bind();
}
```

## Getting Started

### Running Forge Code

You can either run Forge code directly with the interpreter or transpile it to C:

#### 1. Run with Interpreter

```bash
python interpreter.py your_program.forge
```

#### 2. Transpile to C

```bash
python transpile_to_c.py your_program.forge > output.c
gcc output.c -o output -lm
./output
```

## Project Structure

```
.
├── interpreter.py       # Interpreter runtime for executing Forge AST
├── lexer.py             # Tokenizer
├── transpile_to_c.py    # AST to C transpiler
├── templates/           # Jinja2 templates for code generation
└── README.md            # This document
```

## Supported Constructs

Forge supports:

- Variable declarations (`let`)
- Functions with type annotations and return types
- Struct definitions and field access
- Control flow: `if`, `elif`, `else`, `for`, `while`, `match`
- Built-ins: `print`, `input`, `read`, `write`, `len`, `number`, `string`, `hash`
- Lists and arrays (with indexing, `.add`, `.remove`, `.index`)
- Exception handling: `attempt` / `rescue`
- Module loading via `load`

### Example: Using `attempt` / `rescue`

```forge
load "finance.forge"

struct AccountUser {
    balance: float
    numofaccounts: int
    firstName: str
    lastName: str
    accountNumber: int
}

print("Lets get you setup")
let name = input("Enter your name: ")
let lname = input("Enter your last name: ")
let numofaccount: int = input("Enter the amount of accounts you would like to create: ")
let bal: float = input("Enter the amount you would like to deposit: ")
let an: int = ri(1000,9999)
let u = AccountUser(bal, numofaccount, name, lname, an)
let using: bool = true
let withdraws: float = @()
let winfo: StringList = @()
let deposits: float = @()
let dinfo: StringList = @()

while using == true {
    attempt {
        print(name, "Welcome to the bank")
        print("What would you like to do today?")
        print("1. Check your balance")
        print("2. Deposit")
        print("3. Withdraw")
        print("4. Account info")
        let choice: int = input("Enter: ")

        if choice == 1 {
            print("Balance")
            printp(u.balance, 2)
        }
        if choice == 2 {
            let deposit: float = input("Enter your deposit: ")
            let amount: float = u.balance + deposit
            let info1: str = input("Would you like to add a note: ")
            u.balance = amount
            deposits.add(amount)
            if info1 != "no" {
                dinfo.add(info1)
            } else {
                dinfo.add("No Info")
            }
            print(len(deposits))
            printp(u.balance, 2)
        }
        if choice == 3 {
            let withdraw: float = input("Enter the amount you would like to withdraw: ")
            u.balance = u.balance - withdraw
            withdraws.add(withdraw)
            let info: str = input("Would you like to add a note: ")
            if info != "no" {
                winfo.add(info)
            } else {
                winfo.add("No Info")
            }
            print("Withdraw Successful!")
            print("New Balance")
            printp(u.balance, 2)
        }
        if choice == 4 {
            print("Account Number", u.accountNumber)
            print("Deposits: ")
            for let i = 0; i < len(deposits); i++ {
                print("Deposit:")
                printp(deposits[i], 2)
                print("Info:", string(dinfo[i]))
            }
            for let i = 0; i < len(withdraws); i++ {
                print("Withdraws:")
                printp(withdraws[i], 2)
                print("Info:", string(winfo[i]))
            }
        }
    } rescue e {
        print("ERROR:", e)
    }
}
```
### Example: Manual Memory Manipulation

```forge
load "memory.forge"

print("Running memory test")

let block = forge_alloc(1)
forge_memset(block, 70, 1)  # Fill with ASCII 'F'
let block2 = forge_alloc(1)
forge_memset(block2, 79, 1)
let block3 = forge_alloc(1)
forge_memset(block3, 82, 1)
let block4 = forge_alloc(1)
forge_memset(block4, 71, 1)
let block5 = forge_alloc(1)
forge_memset(block5, 69, 1)

print("Buffer:", string(block), string(block2), string(block3), string(block4), string(block5))

forge_free(block)
forge_free(block2)
forge_free(block3)
forge_free(block4)
forge_free(block5)

print("Memory test done.")

let x = @()
x.add("hello")
x.add(42)
print(x)

let buf = forge_alloc(6)
forge_memset(buf, 72, 1)  # 'H'
forge_memset(buf + 1, 105, 1)  # 'i'
forge_memset(buf + 2, 0, 1)  # null-terminate
print(string(buf))  # Outputs "Hi"

let ar = [1, 2, 3]
print(ar[1])

fn mem_eq(a, b, len: number) -> boolean {
    let i = 0
    while i < len {
        if (a + i) != (b + i) {
            return false
        }
        i = i + 1
    }
    return true
}

let person = forge_alloc(8)
forge_memset(person, 74, 1)  # 'J'
forge_memset(person + 4, 21, 1)  # age = 21

fn dump(ptr: pointer, len: number) {
    let i = 0
    while i < len {
        print((ptr + i))
        i = i + 1
    }
}
dump(person, 1)

let heap = forge_alloc(1024)
```

## Runtime Libraries

Transpiled C code depends on helper libraries like:

- `list.h`, `array.h`: dynamic containers
- `fileio.h`: file operations
- `hash.h`: hashing functions
- `runtime.h`: memory and utility helpers
- `exception.h`: setjmp-based error handling

These are included automatically as headers in the generated C code.

## Contributing

Pull requests welcome! Focus areas include:

- Improving parser and error messages
- Adding type inference and generics
- More runtime utilities (e.g. string manipulation, math)
- Garbage collector ideas

## License

MIT License. See `LICENSE` file for details.
