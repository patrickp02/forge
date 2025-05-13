#ifndef FILEIO_H
#define FILEIO_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int write_file(const char* filename, const char* content, const char* mode, int spacing) {
    FILE* f = fopen(filename, mode);
    if (!f) return 0;

    fputs(content, f);
    for (int i = 0; i < spacing; i++) {
        fputc('\n', f);
    }

    fclose(f);
    return 1;
}

char* read_file(const char* filename) {
    FILE* f = fopen(filename, "r");
    if (!f) return NULL;

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    rewind(f);

    char* buffer = malloc(size + 1);
    if (!buffer) {
        fclose(f);
        return NULL;
    }

    fread(buffer, 1, size, f);
    buffer[size] = '\0';
    fclose(f);
    return buffer;
}

#endif
