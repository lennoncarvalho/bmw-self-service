/*
 * edx_shim — small, stable C API over the vendored ediabasx interpreter.
 *
 * The host (Python via ctypes) owns all vehicle I/O. The interpreter never
 * opens a socket: every BEST/2 `xsend` telegram is handed to the registered
 * send callback, which returns the reply telegram (or a failure code).
 *
 * One context is confined to one thread at a time, except
 * `edx_request_break`, which may be called from any thread.
 */
#ifndef EDX_SHIM_H
#define EDX_SHIM_H

#include <stddef.h>
#include <stdint.h>

#define EDX_API_VERSION 1

/* Run/load status codes. */
#define EDX_OK 0
#define EDX_ERR_VM 1       /* interpreter error; see edx_vm_error() */
#define EDX_ERR_ABORT 2    /* send callback returned EDX_SEND_ABORT */
#define EDX_ERR_DEADLINE 3 /* job deadline passed inside the interpreter */
#define EDX_ERR_BREAK 4    /* edx_request_break() */
#define EDX_ERR_ARG 5      /* invalid argument or no SGBD loaded */
#define EDX_ERR_LOAD 6     /* file unreadable or not a PRG/GRP */
#define EDX_ERR_NOMEM 7

/* Send callback results. */
#define EDX_SEND_OK 0    /* reply telegram written to resp/resp_len */
#define EDX_SEND_ERROR 1 /* soft interface error: the SGBD's trap handling decides */
#define EDX_SEND_ABORT 2 /* stop the job; nothing more is sent */

/* Result value types (mirror edxn_result_type_t). */
#define EDX_TYPE_INT 0
#define EDX_TYPE_LONG 1
#define EDX_TYPE_FLOAT 2
#define EDX_TYPE_STRING 3
#define EDX_TYPE_BINARY 4
#define EDX_TYPE_CHAR 5
#define EDX_TYPE_WORD 6
#define EDX_TYPE_DWORD 7
#define EDX_TYPE_BYTE 8

typedef struct edx_ctx edx_ctx_t;

/* `concept` is the first xsetpar value (0 if the SGBD set none). */
typedef int (*edx_send_fn)(void *user, uint32_t concept, const uint8_t *req, size_t req_len,
                           uint8_t *resp, size_t resp_cap, size_t *resp_len);

int edx_api_version(void);

edx_ctx_t *edx_create(void);
void edx_destroy(edx_ctx_t *ctx);

void edx_set_send(edx_ctx_t *ctx, edx_send_fn fn, void *user);
/* Directory searched (case-insensitively) for GRP variants and external tables. */
int edx_set_ecu_dir(edx_ctx_t *ctx, const char *dir);

/* Load a PRG/GRP. `name` is the SGBD file name (basename used as VARIANTE). */
int edx_load_file(edx_ctx_t *ctx, const char *path);
int edx_load_bytes(edx_ctx_t *ctx, const uint8_t *data, size_t len, const char *name);

/* Run a job. `timeout_ms` = 0 disables the interpreter-side deadline. */
int edx_run_job(edx_ctx_t *ctx, const char *job, const char *args, const uint8_t *bin,
                size_t bin_len, uint32_t timeout_ms);
void edx_request_break(edx_ctx_t *ctx);

int edx_vm_error(const edx_ctx_t *ctx);
const char *edx_sgbd_name(const edx_ctx_t *ctx);
int edx_is_group(const edx_ctx_t *ctx);
size_t edx_job_count(const edx_ctx_t *ctx);
const char *edx_job_name(const edx_ctx_t *ctx, size_t index);

/* Results of the last job: set 0 = system set, 1..N = data sets. */
size_t edx_set_count(const edx_ctx_t *ctx);
size_t edx_result_count(const edx_ctx_t *ctx, size_t set);
const char *edx_result_name(const edx_ctx_t *ctx, size_t set, size_t index);
int edx_result_type(const edx_ctx_t *ctx, size_t set, size_t index);
int64_t edx_result_int(const edx_ctx_t *ctx, size_t set, size_t index);
double edx_result_float(const edx_ctx_t *ctx, size_t set, size_t index);
const uint8_t *edx_result_data(const edx_ctx_t *ctx, size_t set, size_t index, size_t *len);

#endif
