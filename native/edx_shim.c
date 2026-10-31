/*
 * edx_shim — heap-allocated context, host send callback and flat result
 * accessors over the vendored ediabasx `edxn_ediabas_t` wrapper.
 *
 * The transport here performs no I/O itself: `xsend` telegrams go to the
 * host callback. A host abort, an explicit break or the job deadline stop
 * the job through the VM's break hook, and no further telegram is passed on.
 */
#define _POSIX_C_SOURCE 200809L

#include "edx_shim.h"

#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "ediabasx/ediabas.h"
#include "ediabasx/prg.h"

#define EDX_PARAM_MAX 64
/* Nominal voltages reported to xbatt/xignit: ENET has no voltage line. */
#define EDX_NOMINAL_MV 12000u

struct edx_ctx {
    edxn_ediabas_t eb;
    edxn_transport_t transport;
    edx_send_fn send;
    void *send_user;
    char *ecu_dir;
    uint32_t params[EDX_PARAM_MAX];
    atomic_bool break_requested;
    bool aborted;
    bool deadline_hit;
    bool deadline_active;
    struct timespec deadline;
    bool results_valid;
    bool loaded;
    int vm_error;
};

/* ── deadline / break hook ─────────────────────────────────────────── */

static bool deadline_passed(edx_ctx_t *ctx) {
    if (!ctx->deadline_active) return false;
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    if (now.tv_sec > ctx->deadline.tv_sec
        || (now.tv_sec == ctx->deadline.tv_sec && now.tv_nsec >= ctx->deadline.tv_nsec)) {
        ctx->deadline_hit = true;
        return true;
    }
    return false;
}

static bool should_stop(edx_ctx_t *ctx) {
    return ctx->aborted || atomic_load(&ctx->break_requested) || deadline_passed(ctx);
}

static bool t_should_break(edxn_transport_t *t) {
    return should_stop((edx_ctx_t *)t->ctx);
}

/* ── transport vtable ──────────────────────────────────────────────── */

static edxn_error_t t_connect(edxn_transport_t *t) {
    (void)t;
    return EDXN_OK; /* the host owns the vehicle connection */
}

static void t_disconnect(edxn_transport_t *t) {
    (void)t;
}

static bool t_is_connected(edxn_transport_t *t) {
    (void)t;
    return true;
}

static edxn_error_t t_send(edxn_transport_t *t, const uint8_t *req, size_t req_len,
                           uint8_t *resp, size_t *resp_len, size_t resp_cap) {
    edx_ctx_t *ctx = (edx_ctx_t *)t->ctx;
    *resp_len = 0;
    if (should_stop(ctx) || !ctx->send) {
        ctx->aborted = ctx->aborted || !ctx->send;
        return EDXN_ERR_TRANSPORT;
    }
    static const uint8_t empty[1] = {0};
    size_t got = 0;
    int rc = ctx->send(ctx->send_user, ctx->params[0], req ? req : empty, req ? req_len : 0, resp,
                       resp_cap, &got);
    if (rc == EDX_SEND_OK && got <= resp_cap) {
        *resp_len = got;
        return EDXN_OK;
    }
    if (rc != EDX_SEND_ERROR) ctx->aborted = true;
    return EDXN_ERR_TRANSPORT;
}

/* xstopf: frequent mode is never started (no transmit_frequent), so stopping
   it is a no-op. Job INITIALISIERUNG routines call it before xsetpar. */
static edxn_error_t t_stop_frequent(edxn_transport_t *t) {
    (void)t;
    return EDXN_OK;
}

static edxn_error_t t_set_parameter(edxn_transport_t *t, uint16_t param, uint32_t value) {
    edx_ctx_t *ctx = (edx_ctx_t *)t->ctx;
    if (param == 0) memset(ctx->params, 0, sizeof(ctx->params));
    if (param < EDX_PARAM_MAX) ctx->params[param] = value;
    return EDXN_OK;
}

static edxn_error_t t_get_parameter(edxn_transport_t *t, uint16_t param, uint32_t *value) {
    edx_ctx_t *ctx = (edx_ctx_t *)t->ctx;
    *value = param < EDX_PARAM_MAX ? ctx->params[param] : 0;
    return EDXN_OK;
}

static uint32_t t_voltage(edxn_transport_t *t) {
    (void)t;
    return EDX_NOMINAL_MV;
}

static const char *t_interface_type(edxn_transport_t *t) {
    (void)t;
    return "ENET";
}

static uint32_t t_interface_version(edxn_transport_t *t) {
    (void)t;
    return 1;
}

/* ── lifecycle ─────────────────────────────────────────────────────── */

int edx_api_version(void) {
    return EDX_API_VERSION;
}

edx_ctx_t *edx_create(void) {
    edx_ctx_t *ctx = (edx_ctx_t *)calloc(1, sizeof(*ctx));
    if (!ctx) return NULL;
    if (edxn_ediabas_init(&ctx->eb) != EDXN_OK) {
        free(ctx);
        return NULL;
    }
    atomic_init(&ctx->break_requested, false);
    edxn_transport_t *t = &ctx->transport;
    t->ctx = ctx;
    t->connect = t_connect;
    t->disconnect = t_disconnect;
    t->send = t_send;
    t->is_connected = t_is_connected;
    t->stop_frequent = t_stop_frequent;
    t->set_parameter = t_set_parameter;
    t->get_parameter = t_get_parameter;
    t->ignition_mv = t_voltage;
    t->battery_mv = t_voltage;
    t->interface_type = t_interface_type;
    t->interface_version = t_interface_version;
    t->should_break = t_should_break;
    edxn_ediabas_set_transport(&ctx->eb, t);
    return ctx;
}

void edx_destroy(edx_ctx_t *ctx) {
    if (!ctx) return;
    edxn_ediabas_free(&ctx->eb);
    free(ctx->ecu_dir);
    free(ctx);
}

void edx_set_send(edx_ctx_t *ctx, edx_send_fn fn, void *user) {
    if (!ctx) return;
    ctx->send = fn;
    ctx->send_user = user;
}

int edx_set_ecu_dir(edx_ctx_t *ctx, const char *dir) {
    if (!ctx || !dir) return EDX_ERR_ARG;
    size_t n = strlen(dir) + 1;
    char *copy = (char *)malloc(n);
    if (!copy) return EDX_ERR_NOMEM;
    memcpy(copy, dir, n);
    free(ctx->ecu_dir);
    ctx->ecu_dir = copy;
    edxn_ediabas_set_sgbd_loader(&ctx->eb, edxn_vm_posix_sgbd_loader, ctx->ecu_dir);
    edxn_ediabas_set_table_loader(&ctx->eb, edxn_vm_posix_table_loader, ctx->ecu_dir);
    return EDX_OK;
}

/* Takes ownership of `bytes` (freed on failure). */
static int load_owned(edx_ctx_t *ctx, uint8_t *bytes, size_t len, const char *name) {
    edxn_prg_t *prg = (edxn_prg_t *)calloc(1, sizeof(*prg));
    if (!prg) {
        free(bytes);
        return EDX_ERR_NOMEM;
    }
    edxn_error_t err = edxn_prg_parse(prg, bytes, len);
    if (err != EDXN_OK) {
        edxn_prg_free(prg);
        free(prg);
        free(bytes);
        ctx->vm_error = (int)err;
        return EDX_ERR_LOAD;
    }
    ctx->results_valid = false;
    ctx->loaded = false;
    err = edxn_ediabas_load_sgbd(&ctx->eb, prg, bytes, name); /* owns prg/bytes now */
    ctx->vm_error = (int)err;
    if (err != EDXN_OK) return err == EDXN_ERR_NOMEM ? EDX_ERR_NOMEM : EDX_ERR_LOAD;
    ctx->loaded = true;
    return EDX_OK;
}

int edx_load_bytes(edx_ctx_t *ctx, const uint8_t *data, size_t len, const char *name) {
    if (!ctx || !data || len == 0 || !name) return EDX_ERR_ARG;
    uint8_t *copy = (uint8_t *)malloc(len);
    if (!copy) return EDX_ERR_NOMEM;
    memcpy(copy, data, len);
    return load_owned(ctx, copy, len, name);
}

int edx_load_file(edx_ctx_t *ctx, const char *path) {
    if (!ctx || !path) return EDX_ERR_ARG;
    FILE *f = fopen(path, "rb");
    if (!f) return EDX_ERR_LOAD;
    long n = -1;
    if (fseek(f, 0, SEEK_END) == 0) n = ftell(f);
    if (n <= 0 || fseek(f, 0, SEEK_SET) != 0) {
        fclose(f);
        return EDX_ERR_LOAD;
    }
    uint8_t *bytes = (uint8_t *)malloc((size_t)n);
    if (!bytes) {
        fclose(f);
        return EDX_ERR_NOMEM;
    }
    size_t got = fread(bytes, 1, (size_t)n, f);
    fclose(f);
    if (got != (size_t)n) {
        free(bytes);
        return EDX_ERR_LOAD;
    }
    const char *name = path;
    for (const char *p = path; *p; p++) {
        if (*p == '/' || *p == '\\') name = p + 1;
    }
    return load_owned(ctx, bytes, got, name);
}

/* ── jobs ──────────────────────────────────────────────────────────── */

int edx_run_job(edx_ctx_t *ctx, const char *job, const char *args, const uint8_t *bin,
                size_t bin_len, uint32_t timeout_ms) {
    if (!ctx || !job || !ctx->loaded) return EDX_ERR_ARG;
    ctx->results_valid = false;
    ctx->aborted = false;
    ctx->deadline_hit = false;
    ctx->vm_error = EDXN_OK;
    ctx->deadline_active = timeout_ms > 0;
    if (ctx->deadline_active) {
        clock_gettime(CLOCK_MONOTONIC, &ctx->deadline);
        ctx->deadline.tv_sec += (time_t)(timeout_ms / 1000u);
        ctx->deadline.tv_nsec += (long)(timeout_ms % 1000u) * 1000000L;
        if (ctx->deadline.tv_nsec >= 1000000000L) {
            ctx->deadline.tv_sec += 1;
            ctx->deadline.tv_nsec -= 1000000000L;
        }
    }
    edxn_error_t err = edxn_ediabas_exec_data(&ctx->eb, job, args ? args : "", bin, bin_len);
    ctx->vm_error = (int)err;
    /* A break requested before or during this job applies to it; clear afterwards. */
    bool broke = atomic_exchange(&ctx->break_requested, false);
    deadline_passed(ctx);
    ctx->deadline_active = false;
    /* The first cause wins: a host abort or stop invalidates any results. */
    if (ctx->aborted) return EDX_ERR_ABORT;
    if (broke) return EDX_ERR_BREAK;
    if (ctx->deadline_hit) return EDX_ERR_DEADLINE;
    if (err != EDXN_OK) return err == EDXN_ERR_NOMEM ? EDX_ERR_NOMEM : EDX_ERR_VM;
    ctx->results_valid = true;
    return EDX_OK;
}

void edx_request_break(edx_ctx_t *ctx) {
    if (ctx) atomic_store(&ctx->break_requested, true);
}

/* ── accessors ─────────────────────────────────────────────────────── */

int edx_vm_error(const edx_ctx_t *ctx) {
    return ctx ? ctx->vm_error : (int)EDXN_ERR_OPERAND;
}

const char *edx_sgbd_name(const edx_ctx_t *ctx) {
    return ctx && ctx->loaded ? ctx->eb.sgbd_name : "";
}

int edx_is_group(const edx_ctx_t *ctx) {
    return ctx && ctx->loaded && ctx->eb.prg->header.version == 0;
}

size_t edx_job_count(const edx_ctx_t *ctx) {
    return ctx && ctx->loaded ? ctx->eb.prg->job_count : 0;
}

const char *edx_job_name(const edx_ctx_t *ctx, size_t index) {
    if (index >= edx_job_count(ctx)) return NULL;
    return ctx->eb.prg->jobs[index].name;
}

static const edxn_result_entry_t *entry(const edx_ctx_t *ctx, size_t set, size_t index) {
    if (!ctx || !ctx->results_valid) return NULL;
    size_t count = 0;
    const edxn_result_set_t *sets = edxn_ediabas_get_sets(&ctx->eb, &count);
    if (!sets || set >= count || index >= sets[set].count) return NULL;
    return &sets[set].entries[index];
}

size_t edx_set_count(const edx_ctx_t *ctx) {
    if (!ctx || !ctx->results_valid) return 0;
    size_t count = 0;
    edxn_ediabas_get_sets(&ctx->eb, &count);
    return count;
}

size_t edx_result_count(const edx_ctx_t *ctx, size_t set) {
    if (set >= edx_set_count(ctx)) return 0;
    size_t count = 0;
    const edxn_result_set_t *sets = edxn_ediabas_get_sets(&ctx->eb, &count);
    return sets[set].count;
}

const char *edx_result_name(const edx_ctx_t *ctx, size_t set, size_t index) {
    const edxn_result_entry_t *e = entry(ctx, set, index);
    return e ? e->name : NULL;
}

int edx_result_type(const edx_ctx_t *ctx, size_t set, size_t index) {
    const edxn_result_entry_t *e = entry(ctx, set, index);
    return e ? (int)e->type : -1;
}

int64_t edx_result_int(const edx_ctx_t *ctx, size_t set, size_t index) {
    const edxn_result_entry_t *e = entry(ctx, set, index);
    return e ? e->value.i : 0;
}

double edx_result_float(const edx_ctx_t *ctx, size_t set, size_t index) {
    const edxn_result_entry_t *e = entry(ctx, set, index);
    return e ? e->value.f : 0.0;
}

const uint8_t *edx_result_data(const edx_ctx_t *ctx, size_t set, size_t index, size_t *len) {
    const edxn_result_entry_t *e = entry(ctx, set, index);
    if (len) *len = 0;
    if (!e || (e->type != EDXN_TYPE_STRING && e->type != EDXN_TYPE_BINARY)) return NULL;
    if (len) *len = e->value.bin.len;
    return e->value.bin.data;
}
