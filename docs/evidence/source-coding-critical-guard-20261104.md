# Source critical-condition coding guard — 2026-11-04

Status: source-recovered and implemented as a generic compiled-contract executor.
This is an actual source precondition, not a hypothetical additional warning or
an owner decision to weaken coding support. No car traffic was sent.

Source APK SHA-256:
`fc6eedeb741cbec49f46c126f8c72dac6a3dd1455f8a993c028695642459b728`.
Root's three full REA records are retained at
`/Users/lennon/BMW-Tool/investigations/source-runtime-20261104/root-critical-coding-evidence.json`,
SHA-256 `efc0252c628e72879465b5bc55b32f1fab2e6050e861d05d9a26d0928e8d9b8a`.
Class names below use the original `parameters.class_name`; decompiler aliases
are not stable artifact coordinates.

| Original class/method | REA record | Observation |
|---|---|---|
| `models.s0$p$a.b` | `ev_769a697ecb9f3868a8629b4e767e7fd218cb4fb14a4603fcf8b7cef796e4a96e` | Only address120/0x78 loads a sticky per-VIN condition; default false triggers its read |
| `models.s0.V` | `ev_9b38c8ba77610055d6f3dc2e3b5dea39820882c0187781d798dd4751e7f32cbf` | Exact request19020C |
| `models.s0$p$a$a.b` | `ev_8a6442d10eb25be4504405859f09811594090987fd065b986bda968d7c690957` | Returned codes801225/801224 set the VIN fact true and the ECU coding-block flag |

The existing source `s0.A` refuses coding when that flag is true. It is not a
generic online-coding flag. The guard's request/address/codes are compiled into
the standalone selection asset from these retained records; application code
contains a generic executor instead of another hardcoded ECU branch list.

`app/coding_guards.py` checks retained state and makes a fresh checked read before
confirmation and again before mutation. Preparation first rereads VIN, so the
observation is not associated solely with cached vehicle identity. Both requests
run through CarWorker/the existing sole protocol owner and use the established
30-second per-read cap.

Evidence is separate from restorable coding backups, in
`<OperationStore parent>/coding-guards/`, using a bounded64KiB, integrity-checked
non-restorable envelope with VIN, source contract, raw request/response and sticky
observation. No QSettings operation state or fake ECU baseline is introduced.
First use legitimately has no cache in the source; a fresh observation must be
persisted before proceeding. Existing corruption or a missing prepared record
blocks writes. Once critical state is observed, empty later DTC memory does not
automatically clear the source sticky fact. Ordinary DTC read/clear functionality
is independent of this coding restriction.

Plans freeze each applicable guard's identity/observation hash; execution requires
that prepared evidence and the same compiled contract, then refetches. Malformed,
negative or unavailable guard responses never become a non-critical result.
Critical blocking identifies the actual ECU in the user notice, states that no
coding write was sent, and preserves that instruction in the operation journal.

One-off checks outside the repository pass: fresh false observations, both
critical codes independently, sticky blocking without another read, corrupt
record zero-send, deleted prepared record zero-send, and rejection of the guard
file by the restorable-baseline loader. A full compiled-asset engine fixture also passes with actual IHKA definition
`000016EE-113-100-006` and F150 `78 0F1D70`: false checks occur before confirmation
and before writes, while a critical code appearing between them blocks all coding
writes and journals ECU-specific no-write instructions. These are synthetic ECU
bytes/fixture pairing, not physical observations. Root owns visual/UI checks and
final full preflight.
