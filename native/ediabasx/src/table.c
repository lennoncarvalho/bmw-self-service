#include "ediabasx/table.h"
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

/* Walk XOR-decoded NUL-terminated strings from column_offset.
   Returns pointer to the string at (row, col), or NULL on OOB. local: the table
   data comes from an untrusted job file, so every step is bounded by `len`
   and the returned string's terminator lies inside the buffer. */
static const char *walk_to_cell(const edxn_prg_table_t *tbl,
                                 const uint8_t *decoded, size_t len,
                                 int row, int col) {
    if (!decoded) return NULL;
    if (col < 0 || col >= tbl->columns) return NULL;
    if (row < 0 || row > tbl->rows)     return NULL;  /* row 0 = header */

    size_t target = (size_t)row * tbl->columns + (size_t)col;
    size_t off = tbl->column_offset;
    if (off >= len) return NULL;

    for (size_t cell = 0; cell < target; cell++) {
        const uint8_t *nul = memchr(decoded + off, 0, len - off);
        if (!nul) return NULL;
        off = (size_t)(nul - decoded) + 1;  /* skip NUL */
        if (off >= len) return NULL;
    }

    if (!memchr(decoded + off, 0, len - off)) return NULL;
    return (const char *)(decoded + off);
}

int edxn_table_find_column(const edxn_prg_table_t *tbl,
                            const uint8_t *decoded, size_t len, const char *name) {
    for (int col = 0; col < tbl->columns; col++) {
        const char *hdr = walk_to_cell(tbl, decoded, len, 0, col);
        if (!hdr) continue;
        /* Case-insensitive compare */
        const char *a = hdr;
        const char *b = name;
        while (*a && *b && toupper((unsigned char)*a) == toupper((unsigned char)*b)) {
            a++;
            b++;
        }
        if (*a == '\0' && *b == '\0')
            return col;
    }
    return -1;
}

const char *edxn_table_get_cell(const edxn_prg_table_t *tbl,
                                 const uint8_t *decoded, size_t len, int row, int col) {
    return walk_to_cell(tbl, decoded, len, row, col);
}

int edxn_table_seek(const edxn_prg_table_t *tbl, const uint8_t *decoded,
                     size_t len, int col, const char *value) {
    for (int row = 1; row <= tbl->rows; row++) {
        const char *cell = walk_to_cell(tbl, decoded, len, row, col);
        if (!cell) continue;
        const char *a = cell;
        const char *b = value;
        while (*a && *b && toupper((unsigned char)*a) == toupper((unsigned char)*b)) {
            a++; b++;
        }
        if (*a == '\0' && *b == '\0')
            return row;
    }
    return -1;
}

int edxn_table_seek_u(const edxn_prg_table_t *tbl, const uint8_t *decoded,
                       size_t len, int col, uint32_t value) {
    for (int row = 1; row <= tbl->rows; row++) {
        const char *cell = walk_to_cell(tbl, decoded, len, row, col);
        if (!cell) continue;
        uint32_t cell_val = (uint32_t)strtoul(cell, NULL, 0);
        if (cell_val == value)
            return row;
    }
    return -1;
}
