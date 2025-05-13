#ifndef EXCEPTION_H
#define EXCEPTION_H

#include <setjmp.h>
#include <stdio.h>

typedef struct {
    jmp_buf env;
    const char* error;
    int has_error;
} ExceptionContext;

static ExceptionContext __context;

#define Attempt if (!setjmp(__context.env))
#define Rescue else

static inline void raise(const char* msg) {
    __context.error = msg;
    __context.has_error = 1;
    longjmp(__context.env, 1);
}

#endif
