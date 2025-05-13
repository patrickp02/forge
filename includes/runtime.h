#ifndef FORGE_RUNTIME_H
#define FORGE_RUNTIME_H

#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include <netinet/in.h>
#include <arpa/inet.h>

// =====================
// Memory intrinsics
// =====================

static inline void* forge_alloc(int size) {
    return malloc(size);
}

static inline void forge_free(void* ptr) {
    free(ptr);
}

static inline void forge_memcpy(void* dst, void* src, int size) {
    memcpy(dst, src, size);
}

static inline void forge_memset(void* dst, int value, int size) {
    memset(dst, value, size);
}

// =====================
// Other helpers
// =====================

static inline int as_str_index(const char* str, char ch) {
    for (int i = 0; str[i]; i++) {
        if (str[i] == ch) return i;
    }
    return -1;
}

typedef struct {
    char* type;
    char* value;
} Node;

static inline Node make_node(const char* type, const char* value) {
    Node node;
    node.type = strdup(type);
    node.value = strdup(value);
    return node;
}
static inline void free_node(Node n) {
    if (n.type) {
        free(n.type);
        n.type = NULL;
    }
    if (n.value) {
        free(n.value);
        n.value = NULL;
    }
}


static inline char* node_to_string(Node n) {
    char* buf = malloc(128);
    snprintf(buf, 128, "%s:%s", n.type, n.value);
    return buf;
}


static inline intptr_t make_sockaddr(int port_netorder) {
    struct sockaddr_in* addr = malloc(sizeof(struct sockaddr_in));
    memset(addr, 0, sizeof(struct sockaddr_in));
    addr->sin_family = AF_INET;
    addr->sin_port = port_netorder;
    addr->sin_addr.s_addr = INADDR_ANY;
    return (uintptr_t)addr;
}

#endif
