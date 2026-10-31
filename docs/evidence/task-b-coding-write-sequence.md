# Task B — Coding write UDS sequence (F/G-series, ENET)

Status: recovered from static source. Protocol behavior only.

**Source:** `sources/BimmerCode_v4.25.04-12743.apk`
(SHA256 `fc6eedeb741cbec49f46c126f8c72dac6a3dd1455f8a993c028695642459b728`),
read as smali under `bimmercode_extracted/smali/de/appomotive/bimmercode/`.
Recovery method: static disassembly (grep/sed), no runtime, no vehicle traffic,
no REA binary session. Supports owner decision D-66: records only the wire
sequence for applying byte-level coding blocks; contains no coding-database
content and no key-derivation algorithm.

Raw notes: `/Users/lennon/BMW-Tool/investigations/coding-write-20261030/raw-notes.md`.

## Transport context

ENET adapter is `c.a.m` (`ENETAdapter`, extends `c.a.b`). HSFZ framing and the
request/ACK/response loop live in `c.a.o`. Bluetooth/ELM adapters are `c.a.d`
and its subclasses `c.a.h` / `c.a.j`; several steps branch on transport, and the
ENET branch is recorded below.

HSFZ request frame (`c.a.o.doInBackground`, Evidence class/offset in raw notes):
`[len=payload+2 : BE32][00 01][F4][ecuAddr][payload…]`, source address `0xF4`,
payload-type `0x0001`. The adapter first reads a type-`0x02` ACK echoing the
request, then the type-`0x01` response.

## Orchestration — `codingtasks/CodingDataWriter`

Constructed with `(n0 ecu, ArrayList<k.j> blocks, String cps)`. State enum
`CodingDataWriter$i` = PREPARE, AUTHENTICATE, WRITE, SIGNATURE_CHECK, WRITE_CPS,
RESET, CLEAR_ERRORS. Each step is a task (subclass of `codingtasks/e`) run with a
`codingtasks/f` callback; success chains to the next step, any negative/exception
aborts the whole chain. Resolved order:

`PREPARE → (AUTHENTICATE if a security entry exists) → WRITE(all blocks) →
SIGNATURE_CHECK → WRITE_CPS → RESET → CLEAR_ERRORS`.

## Step-by-step wire contract (ENET)

### 1. Diagnostic session — PREPARE (`codingtasks/n`)
Three sequential requests, each requiring a positive response SID `0x50`:
```
10 01      (default session)
10 03      (extended diagnostic session)
10 41      (BMW programming/coding session variant)
```

### 2. Security access — AUTHENTICATE (`codingtasks/l`, params `codingtasks/m`)
Runs only when `n0.s().c()` (model `r0` → `k.v` security entry) is non-null; ECUs
with no stored entry are not written by this path.
```
27 01 FF FF FF FF        request seed (expect SID 0x67)
→ seed = response[2..]
27 02 <key bytes>        send key (expect SID 0x67)
```
Key derivation: variant id → `e.d.f(id, e.g.f)` → `e.e`; `e.a.b(seedBlock, key)`.
The derivation itself lives in `de.appomotive.bimmercode.e.*` and is not recorded
here (shapes only). A write that reaches production ECUs requires a valid `27 02`.

### 3. Coding write — WRITE (`codingtasks/y`, params `codingtasks/z`)
Iterates the block list. Each block `k.j` is one complete DID payload (no UDS-level
chunking):
```
2E <DID_hi> <DID_lo> <block bytes…>      (expect SID 0x6E per block)
```
DID = `k.j.c()` (Integer, big-endian 2 bytes); data = `k.j.b()`. On ENET a
TesterPresent `3E 80` (suppress positive response) is sent before the first block
and between blocks. Progress/ETA is reported from response timing. First negative
response aborts.

### 4. Block checksum (`k/j.f` + `k/j.a`)
Before the write, a block may have a checksum byte recomputed and embedded in its
data. Position (and an invert flag) come from the coding definition metadata
(`models.w`). Algorithm: one-byte XOR of every block byte except the checksum slot,
optionally XOR `0xFF`. This is a plain XOR-8 field inside the block payload, not a
cryptographic signature. (When presets are learned by diffing full before/after
snapshots per D-66, the already-correct checksum byte is part of the captured bytes.)

### 5. SIGNATURE_CHECK
ECU-address dependent (`CodingDataWriter.e()`): DME-class addresses `0x12`/`0x50`
use `codingtasks/t`, others use `codingtasks/s`.
- On ENET, both reduce to a TesterPresent keep-alive: `3E 80`. `t` adds a ~3000 ms
  delay (base `e.i` `postDelayed`).
- The RoutineControl `31 01 0F 01` appears only on the Bluetooth/CAN branch
  (`codingtasks/s.l()`, adapters `c.a.h`/`c.a.j`); it is not emitted over ENET.

### 6. CPS write — WRITE_CPS (`codingtasks/w`, params `codingtasks/x`)
Writes a coding stamp to DID `37FE`:
```
2E 37 FE <last 7 chars of the CPS string, US-ASCII>    (expect SID 0x6E)
```
The CPS string is supplied to the writer constructor.

### 7. ECU reset — RESET (`codingtasks/r`)
Address dependent: `0x50` → `10 01` (return to default session); other ECUs →
`11 01` (ECU hard reset). Up to 3 attempts (`r.n()`).

### 8. CLEAR_ERRORS (`codingtasks/c`)
```
14 FF FF FF     (clear all diagnostic information)
```
On success the writer signals completion.

## Completion and negative-response handling

- Positive-response SIDs checked per step: `0x50` (session), `0x67` (security),
  `0x6E` (write), `0x6E` (CPS). Any first byte `0x7F` is treated as negative and
  aborts that step (`e.h()` → `CodingTaskException`).
- NRC `0x78` (response pending) is absorbed in transport (`c.a.o.d`): on `7F … 78`
  it re-reads with a 7000 ms window until a non-`0x78` response or timeout. Normal
  ack/data timeout is 1000 ms.
- NRCs `0x22` / `0x31` / `0x33` are not individually branched; they fall into the
  generic negative-response abort.
- Completion is response-confirmed (positive SIDs per step) plus the final reset and
  clear; there is no post-write read-back of the written DID in this path.

## Differences per ECU class

- DME-class addresses `0x12`/`0x50`: SIGNATURE_CHECK uses the `t` keep-alive with a
  ~3 s delay; RESET for `0x50` uses `10 01` instead of `11 01`.
- BDC/FEM and other body/headunit ECUs over ENET: `11 01` reset, `3E 80`
  signature-check keep-alive, `3E 80` between write blocks.
- The BDC/FEM-specific `31 01 0F 01` routine was found only on the Bluetooth/CAN
  transport path, not ENET.

## Open questions

1. No ENET packet capture yet confirms the recovered bytes on a live BDC/KOMBI/NBT.
   This is static-only; byte order and the `10 41` session need a capture to pin.
2. The invert flag and checksum slot for each DID come from the coding definition
   (`models.w`); for app-composed blocks (not snapshot-diff presets) that metadata
   must be sourced independently.
3. Security `27 02` requires the variant-specific key path; whether any target
   coding DIDs are writable without `27` on a given ECU is unverified per variant.
4. The CPS string origin/format (what the last 7 ASCII chars encode) is not traced.
5. KOMBI (`komb*`) coding-write address class not individually confirmed against the
   ISTA PRG cross-check in this pass.
