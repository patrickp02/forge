#include "list.h"
#include <stdlib.h>

#define INITIAL_CAPACITY 4

List list_create() {
    List list;
    list.items = malloc(INITIAL_CAPACITY * sizeof(int));
    list.capacity = INITIAL_CAPACITY;
    list.count = 0;
    return list;
}

void list_add(List* list, int value) {
    if (list->count >= list->capacity) {
        list->capacity *= 2;
        list->items = realloc(list->items, list->capacity * sizeof(int));
    }
    list->items[list->count++] = value;
}
