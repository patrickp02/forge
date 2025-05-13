#ifndef ARRAY_H
#define ARRAY_H
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

// Define a generic array structure
typedef struct {
    void* data;      // Pointer to the array data
    size_t element_size; // Size of each element
    size_t length;   // Number of elements in the array
} Array;

// Function to create an array
Array array_create(size_t element_size, size_t length) {
    Array arr;
    arr.data = malloc(element_size * length);
    arr.element_size = element_size;
    arr.length = length;
    return arr;
}

// Function to get an element from the array
void* array_get(Array* arr, size_t index) {
    if (index >= arr->length) {
        fprintf(stderr, "Array index out of bounds\n");
        exit(EXIT_FAILURE);
    }
    return (char*)arr->data + (index * arr->element_size);
}

// Function to set an element in the array
void array_set(Array* arr, size_t index, void* value) {
    if (index >= arr->length) {
        fprintf(stderr, "Array index out of bounds\n");
        exit(EXIT_FAILURE);
    }
    memcpy((char*)arr->data + (index * arr->element_size), value, arr->element_size);
}
static inline void array_to_string(Array* arr, char* buffer, size_t size) {
    buffer[0] = '\0';
    for (int i = 0; i < arr->length; i++) {
        char temp[32];
        snprintf(temp, sizeof(temp), "%.2f", ((double*)arr->data)[i]);
        strncat(buffer, temp, size - strlen(buffer) - 1);
        if (i < arr->length - 1) {
            strncat(buffer, ", ", size - strlen(buffer) - 1);
        }
    }
}

// Function to free the array
void array_free(Array* arr) {
    free(arr->data);
}

#endif // ARRAY_H