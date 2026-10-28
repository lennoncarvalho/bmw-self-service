# Initial audit and readiness findings

Date: 2026-10-28. Baseline: `129d181d5ab4ca770e89de59ecb5189e6f9643a6`,
branch `fix/hsfz-ack-handling`, clean index/worktree before this audit.
At the initial audit, [PR #8](https://github.com/lennoncarvalho/bmw-self-service/pull/8)
had the same head. That documentation cleanup changed no runtime code. The later
existing-review follow-up changed transport/worker code; see its status below.
Neither phase attests that any car operation is correct.

## Outcome

**Later vehicle evidence:** the first retained read-only session now confirms
HSFZ discovery/TCP/session/VIN on the owner's setup. Optional reads were rejected
and DTC coverage was gateway-only. See [the session report](23-first-vehicle-session.md)
and [REA recovery plan](../tasks/rea-protocol-recovery.md). The audit baseline
and earlier unvalidated-fix statements below are historical, not current claims
that no VIN connection has worked.

The app is **not production ready**. At the initial audit, no successful
end-to-end connection had been established. A historical PR excerpt reported
gateway/UDS traffic including VIN, but the original `uds.log` was empty. The
later session above now supplies retained traffic. Both “no network contact”
and “all vehicle reads work” remain inaccurate descriptions.

All 28 original project-owned Markdown files were read. Fifty ignored reference
Markdown files were inventoried and screened, with focused reading of relevant
transport/PRG material; third-party VM internals were not independently certified.
The [document index](README.md) records per-file standing. Sources, databases and
ignored reference repositories were preserved.

## Findings that should drive the next review

These findings describe the audit baseline above. Some predate PR #8; confirm
introduction with the diff/history before calling them regressions. Consult the
follow-up status below before treating every baseline statement as current.

| ID / priority | Evidence and failure consequence | Required resolution |
|---------------|----------------------------------|---------------------|
| A-01 / P0 | `ui/service_history_page.py: ServiceHistoryReadWorker.do_work` sends `31 01 A0 81`, identified elsewhere as an add routine. Loading a page invokes an unverified potentially mutating operation. | Establish a real read-only contract before vehicle use; review disabling the unsupported path |
| A-02 / P0 | `CodingWriteWorker.do_work` falls back to `bytes([current UI index])` when live bytes/selection mapping is unavailable; it accepts responses without validating application success. | Fail closed without complete verified baseline/encoder, check responses and readback |
| A-03 / P0 | `CodingPage._save_backup` stores categories in `manifest.json`, without raw ECU data, VIN or software identity. Backups restoration changes UI state. | Implement a restorable format and verified vehicle restore before advertising rollback |
| A-04 / P1 | `MainWindow._connect_real` always calls HSFZ discovery even for DoIP, then creates DoIPConnection without `activate_routing`. Its activation method elsewhere emits a four-byte payload instead of seven. | Correct discover/activate/identify flow from primary evidence |
| A-05 / P1 | HSFZ returns the first diagnostic frame without checking source/target or UDS correlation; pending/late responses can be returned to another request. | Review transaction ownership, pending responses, timeout recovery and matching |
| A-06 / P1 | `_recv_hsfz_message` always reads eight bytes; short/control frames have type-specific bodies. Short drains suppress timeouts and can discard partial reads. | Frame six-byte base header first; retain partial bytes or invalidate stream |
| A-07 / P1 | DoIP `_lock` exists but `send_uds` does not acquire it. ACK/response are consumed as exactly two frames; no general NACK/alive dispatch. | One serialized dispatcher with validated routing, control messages and response correlation |
| A-08 / P1 | Main-window keepalive QTimer callbacks call synchronous network methods. Coding category construction also contains real-car reads outside a CarWorker. | Trace every caller; move all blocking I/O off GUI thread, including timers and shutdown waits |
| A-09 / P1 | Post-connect DIDs/codecs assume FA XML, fixed SVT structure, F18A I-level, F406 mileage, F40C voltage. Coding chooses first available variant and probes unrelated candidates. | Trace mappings in source artifacts and match exact gateway/ECU/software; unknown stays unavailable |
| A-10 / P1 | macOS discovery interface filtering includes Wi-Fi `enX` and labels by index. DoIP discovery ignores its interface argument; TCP is not scoped to selection. | Detect actual wired link and bind validated selected interface on both transports |
| A-11 / P1 | DHCP pools use link-local addresses. macOS startup ignores subprocess status; Windows returns false; stop routines kill services globally. | Specify network UX and scoped owned lifecycle before enabling fallback |
| A-12 / P1 | Service-history write sends unproven ASCII arguments under `0x2E`; docs conflict with `0x31`. A positive SID is treated as success without business validation/readback. | Reopen protocol research, preserve byte evidence, specify append/replace independently |
| A-13 / P1 | Fault-type lookup uses DTC status semantics, snapshot identification invents timestamps/km, negative paths can hide unread ECUs. | Correct format semantics and explicitly show incomplete scans; verify emissions MIL independently |
| A-14 / P1 | Backup format, known-good readback, multi-change block composition and interrupted-write recovery are not implemented to owner requirements. | Review shared write engine across all write screens; preserve baseline/intended/observed states |
| A-15 / P2 | `Crypto.Cipher.AES` is a runtime import but requirements omit its distribution. Venv reports Python 3.15.2 while CI/config target 3.13. | Separate dependency/toolchain repair with fresh-install verification |
| A-16 / P2 | DTC schema key omits ECU; arbitrary `LIMIT 1` mixes table types. `mode=ro` is described as thread safety, which it does not provide. | Specify description ambiguity and connection ownership; inspect extraction collisions |
| A-17 / P2 | Assets are referenced relative to working directory in UI; ignored coding data lacks a committed acquisition/integrity manifest. Release builds are unverified. | Verify asset/dependency closure and platform packaging outside checkout |

P0 means a potentially mutating or misleading recovery path, not proof that the
operation damaged a vehicle. These issues are recorded for code review, not
silently repaired during a documentation task.

## Existing PR review follow-up (2026-10-28)

[Per-comment dispositions and verification](../tasks/pr-8-review-followup.md)
cover all 24 inline threads and two additional review-body findings. This was a
review of the existing comments, not a complete re-audit of every application
path. Six findings were already addressed, fifteen required repairs and five
were non-actionable suggestions/claims.

| Baseline issue | Current source status after that follow-up |
|----------------|-------------------------------------------|
| A-04 | Seven-byte standard routing activation is validated and invoked before DoIP identity reads; invalid/missing VIN no longer reports connected. Discovery/transport selection and addresses still need variant evidence. |
| A-05 | Endpoint/SID and supported echo matching, pending handling and late-response ownership implemented; vehicle behavior remains unvalidated. |
| A-06 | Six-byte base parser and persistent fragment buffers implemented; no real gateway replay/validation yet. |
| A-07 | Complete DoIP exchanges now serialize and dispatch ACK/NACK/alive traffic; broader DoIP discovery is still open. |
| A-08 | Keepalive I/O moved to a CarWorker with cooperative lifecycle cleanup. Coding-page I/O and other application paths remain to review. |
| A-10 | Adapter filter duplication removed; actual wired-link detection, labels and interface-bound networking remain open. |
| A-15 | PyCryptodome 4.2.0 now declared after fresh CI exposed the missing AES dependency. Local Python 3.15 versus target 3.13 and release packaging validation remain open. |

The other audit findings remain open. In particular, these fixes do not authorize
running the unsupported service-history/coding paths against a vehicle. The
owner's no-automated-suite policy remains unchanged; static gates and app startup
were checked, with no vehicle or visual DEMO acceptance claimed.

## Read-only capture preparation (after PR #8 merge)

See [the validation contract](22-read-only-validation.md) and
[implementation record](../tasks/read-only-car-capture.md). A-01's potentially
mutating automatic history read is disabled at the page and worker boundary.
Live coding now reports unavailable instead of selecting a guessed variant,
probing on the GUI thread or showing mock values; its underlying read/write
contract (A-02/A-03/A-09/A-14) is not implemented by this guard.

An explicit --read-only launch enforces allowed read/session requests at both
transports and disables automatic DHCP fallback. This constrains the validation
run; general networking (A-10/A-11), packaging and default-mode write validation
remain open. Debug logging now preserves control frames, fragments, transaction
and worker context in unique session files.

For A-13, 59 02 records now start at offset 3 with echo/alignment validation,
incomplete results remain incomplete and the unsupported MIL/snapshot codecs
are removed from live reads. DTC descriptions use a separate worker-owned SQLite
connection and require an exact ECU/table match; aliases/extraction collisions
and complete fleet coverage remain unresolved (A-16). No vehicle validation is
implied by these changes or the static gate.

## Documentation defects corrected

- Removed blind “all specs authoritative” handling; evidence and owner decisions
  now take precedence over contradicted historical examples.
- Reopened service-history SID/DID/RID and encoder claims; a job-name prefix or
  local file format cannot establish transmitted bytes.
- Corrected HSFZ base-header handling, DoIP header/activation structure, UDS
  negative/pending semantics and DTC record/snapshot distinctions.
- Withdrew unsupported universal ECU counts, transport-by-series, fixed FA/SVT
  encodings, generic mileage/voltage mappings and “all gaps resolved” claims.
- Corrected SQLite threading and total-row/translation claims. The read-only
  database query measured 88,580 rows and 71,439 nonempty English descriptions.
- Corrected stale test-suite claims, resume instructions and root capability
  status. The owner reaffirmed the no-test-suite policy in this chat.
- Coding/history write screens require backup and readback. Fault clearing is
  explicitly exempt from saved reports/backups, per the owner's follow-up.

## Skills and tooling

`.agents/skills` was absent. Three reviewed upstream skills were installed using
`npx skills@1.7.4` with pinned Git references: PySide6 reviewer, Python error
handling and REA. Project skills cover spec/evidence workflow, Python correctness,
SQLite, BMW transport, vehicle-write integrity and requirements interviewing.
See [provenance and setup](../.agents/README.md) and `skills-lock.json`.

The upstream Qt skill's reference links were broken and some general advice
conflicted with the app's chosen architecture. A local overlay fixes routing
and bounds that advice. No QML, model/view or asyncio migration is authorized.

REA CLI 6.8.0 responds under existing Node 24.22.1. Its doctor reports no Codex
registration and no configured JADX/native analysis engine; no usable JDK was
found by `java_home`. The skill alone does not enable APK/native decompilation.
No host MCP configuration or unrelated software was altered. The REA
skill is pinned to the CLI 6.8.0 release (metadata version 49); obey actual schemas.

## Verification and limits

Baseline `scripts/preflight.sh` passed all three full-target checks: Ruff lint,
Ruff formatting (18 files), mypy (18 files). Local execution used Python 3.15.2;
this is not evidence of a Python 3.13 run. CI also includes `pip-audit`, outside
the three-command local script; no dependency-security audit result is claimed.

Final cleanup verification is recorded in `tasks/audit-verification.md`.
No automated suite, vehicle requests, DHCP/elevation action, hardware validation,
UI acceptance session or platform release build was performed. No push, PR
modification, merge or message to another chat was made. PR #8 was attached
for the next review.

## Recommended next work, after remaining behavior decisions

1. Review PR #8 against its base, separating new regressions from older app
   defects. Capture exact findings and only then make scoped fixes.
2. Establish a read-only F48/NBT connection baseline: adapter/route, discovery,
   full HSFZ frame dispatch, correlated VIN and diagnostic session timing.
3. Validate vehicle data/DTC reads with exact variant evidence. Suppress automatic
   unsupported history/coding operations during that connection validation.
4. Define and implement backup/current/intended/readback files and recovery UX.
   Approve each real-car write path only after its encoder and readback exist.
5. Expand transport/ECU coverage from source apps with retained evidence, then
   package and validate each supported platform. Keep coverage status explicit.
