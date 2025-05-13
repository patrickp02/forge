#ifndef LIST_H
#define LIST_H

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

#define INITIAL_CAPACITY 4
#define TOKEN_NUMBER 1
#define TOKEN_STRING 2
#define TOKEN_ID 3


// ==============================
// 🧮 Generic List of doubles
// ==============================

typedef struct {
    double* items;
    int size;
    int capacity;
} List;

static inline List list_create() {
    List list;
    list.size = 0;
    list.capacity = INITIAL_CAPACITY;
    list.items = malloc(sizeof(double) * list.capacity);
    return list;
}

static inline void list_add(List* list, double value) {
    if (list->size == list->capacity) {
        list->capacity *= 2;
        list->items = realloc(list->items, sizeof(double) * list->capacity);
    }
    list->items[list->size++] = value;
}

static inline void list_add_str(List* list, const char* str) {
    char* copy = strdup(str);
    list_add(list, (double)(intptr_t)copy);
}

static inline char* list_get_str(List* list, int index) {
    return (char*)(intptr_t)(list->items[index]);
}

static inline void list_remove(List* list, double value) {
    for (int i = 0; i < list->size; ++i) {
        if (list->items[i] == value) {
            for (int j = i; j < list->size - 1; ++j) {
                list->items[j] = list->items[j + 1];
            }
            list->size--;
            return;
        }
    }
}

static inline int list_index(List* list, double value) {
    for (int i = 0; i < list->size; ++i) {
        if (list->items[i] == value) {
            return i;
        }
    }
    return -1;
}

static inline void list_free(List* list) {
    free(list->items);
}

static inline void list_to_string(List* list, char* buffer, size_t buffer_size) {
    buffer[0] = '\0';
    for (int i = 0; i < list->size; i++) {
        char temp[64];
        double value = list->items[i];

        if (value > 100000.0) {
            char* s = (char*)(intptr_t)value;
            snprintf(temp, sizeof(temp), "\"%s\"", s);
        } else {
            snprintf(temp, sizeof(temp), "%.2f", value);
        }

        strncat(buffer, temp, buffer_size - strlen(buffer) - 1);
        if (i < list->size - 1) {
            strncat(buffer, ", ", buffer_size - strlen(buffer) - 1);
        }
    }
}

// ==============================
// 📜 StringList
// ==============================

typedef struct {
    char** items;
    int size;
    int capacity;
} StringList;

static inline StringList string_list_create() {
    StringList list;
    list.size = 0;
    list.capacity = INITIAL_CAPACITY;
    list.items = malloc(sizeof(char*) * list.capacity);
    return list;
}

static inline void string_list_add(StringList* list, const char* str) {
    if (list->size == list->capacity) {
        list->capacity *= 2;
        list->items = realloc(list->items, sizeof(char*) * list->capacity);
    }
    list->items[list->size++] = strdup(str);
}

static inline void string_list_free(StringList* list) {
    for (int i = 0; i < list->size; i++) {
        free(list->items[i]);
    }
    free(list->items);
}

// ==============================
// 🧾 TokenList (NEW!)
// ==============================

typedef struct {
    int type;
    char* value;
    int line;
    int column;
} Token;

typedef struct {
    Token* items;
    int size;
    int capacity;
} TokenList;

static inline TokenList token_list_create() {
    TokenList list;
    list.size = 0;
    list.capacity = INITIAL_CAPACITY;
    list.items = malloc(sizeof(Token) * list.capacity);
    return list;
}

static inline void token_list_add(TokenList* list, Token tok) {
    if (list->size == list->capacity) {
        list->capacity *= 2;
        list->items = realloc(list->items, sizeof(Token) * list->capacity);
    }
    list->items[list->size++] = tok;
}

static inline Token token_list_get(TokenList* list, int index) {
    return list->items[index];
}
static inline Token make_token(int type, const char* value, int line, int column) {
    Token tok;
    tok.type = type;
    tok.value = strdup(value);  // make sure to free later!
    tok.line = line;
    tok.column = column;
    return tok;
}

static inline void free_token(Token t) {
    if (t.value) free(t.value);
}

static inline int token_list_len(TokenList* list) {
    return list->size;
}


static inline void token_list_free(TokenList* list) {
    for (int i = 0; i < list->size; i++) {
        free_token(list->items[i]);
    }
    free(list->items);
    list->items = NULL;
    list->size = 0;
    list->capacity = 0;
}

#endif
