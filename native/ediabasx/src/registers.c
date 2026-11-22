#include "ediabasx/registers.h"
#include <stdlib.h>
#include <string.h>

edxn_error_t edxn_reg_resize_s(edxn_registers_t *r, size_t capacity) {
    if (capacity == 0 || capacity > EDXN_MAX_ARRAY_SIZE)
        return EDXN_ERR_INVALID_PRG;
    if (capacity == r->s_capacity) return EDXN_OK;
    uint8_t *storage = (uint8_t *)realloc(r->s, EDXN_S_REG_COUNT * capacity);
    if (!storage) return EDXN_ERR_NOMEM;
    r->s = storage;
    r->s_capacity = capacity;
    return EDXN_OK;
}

void edxn_reg_reset(edxn_registers_t *r) {
    memset(r->bytes, 0, EDXN_NUM_REG_BYTES);
    if (r->s) memset(r->s, 0, EDXN_S_REG_COUNT * r->s_capacity);
    memset(r->s_len, 0, sizeof(r->s_len));
    for (int i = 0; i < EDXN_F_REG_COUNT; i++) {
        r->f[i] = 0.0;
    }
}

uint8_t edxn_reg_get_b(const edxn_registers_t *r, int idx) {
    return r->bytes[idx];
}

void edxn_reg_set_b(edxn_registers_t *r, int idx, uint8_t val) {
    r->bytes[idx] = val;
}

uint8_t edxn_reg_get_a(const edxn_registers_t *r, int idx) {
    return r->bytes[idx + 16];
}

void edxn_reg_set_a(edxn_registers_t *r, int idx, uint8_t val) {
    r->bytes[idx + 16] = val;
}

uint16_t edxn_reg_get_i(const edxn_registers_t *r, int idx) {
    int off = idx * 2;
    return (uint16_t)r->bytes[off] | ((uint16_t)r->bytes[off + 1] << 8);
}

void edxn_reg_set_i(edxn_registers_t *r, int idx, uint16_t val) {
    int off = idx * 2;
    r->bytes[off]     = (uint8_t)(val & 0xFF);
    r->bytes[off + 1] = (uint8_t)(val >> 8);
}

uint32_t edxn_reg_get_l(const edxn_registers_t *r, int idx) {
    int off = idx * 4;
    return (uint32_t)r->bytes[off]
         | ((uint32_t)r->bytes[off + 1] << 8)
         | ((uint32_t)r->bytes[off + 2] << 16)
         | ((uint32_t)r->bytes[off + 3] << 24);
}

void edxn_reg_set_l(edxn_registers_t *r, int idx, uint32_t val) {
    int off = idx * 4;
    r->bytes[off]     = (uint8_t)(val & 0xFF);
    r->bytes[off + 1] = (uint8_t)((val >> 8) & 0xFF);
    r->bytes[off + 2] = (uint8_t)((val >> 16) & 0xFF);
    r->bytes[off + 3] = (uint8_t)((val >> 24) & 0xFF);
}

const uint8_t *edxn_reg_get_s(const edxn_registers_t *r, int idx, size_t *len) {
    *len = r->s_len[idx];
    return r->s + (size_t)idx * r->s_capacity;
}

void edxn_reg_set_s(edxn_registers_t *r, int idx, const uint8_t *data, size_t len) {
    if (len > r->s_capacity) len = r->s_capacity;
    if (len > 0) memmove(r->s + (size_t)idx * r->s_capacity, data, len);
    r->s_len[idx] = len;
}

void edxn_reg_clear_s(edxn_registers_t *r, int idx) {
    memset(r->s + (size_t)idx * r->s_capacity, 0, r->s_capacity);
    r->s_len[idx] = 0;
}

double edxn_reg_get_f(const edxn_registers_t *r, int idx) {
    return r->f[idx];
}

void edxn_reg_set_f(edxn_registers_t *r, int idx, double val) {
    r->f[idx] = val;
}
