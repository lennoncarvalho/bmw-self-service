# Task A — migrate standard protocols to libraries

Status: ready to start in a new implementation session; no migration done yet.
Spec: [doc 25](../docs/25-library-migration-spec.md).
Evaluation and artifact hashes: [doc 24](../docs/24-protocol-library-evaluation.md).
Next task: [Task B — REA feature recovery](rea-protocol-recovery.md).

## Start here

Read `AGENTS.md`, `SESSION-PROMPT.md`, docs 19–25 and the Python/BMW protocol
skills. Inspect the current checkout and PR state; preserve other work. Create
a fresh `codex/` implementation branch from current main. The planning PR is
not a branch for app code. Record the concrete files/API/ownership plan here
before implementation. Consult original library source, not REA, for ordinary
open-source library behavior. Use [doc 27](../docs/27-rea-source-guide.md) when
a BMW-specific uncertainty requires source-app evidence.

## Work checklist

- [ ] A1: Map existing send/read/keepalive/cancel callers; specify a single socket
  owner, raw transport boundary, service client and operation deadline context.
- [ ] A2: Integrate udsoncan standard services and exception/result mapping;
  preserve response/echo/NRC checks, pending timing and outstanding ownership.
- [ ] A3: Integrate Scapy HSFZ behind a small adapter; verify controls, source
  binding, send failures, framing bounds, logging and fragmentation behavior.
- [ ] A4: Integrate doipclient behind the same API; resolve each doc 24 boundary,
  especially resends, ACK ordering, address selection and total deadline.
- [ ] A5: Route CarWorker/keepalive and compatibility callers through the one
  owner; remove superseded standard UDS/transport loops. Preserve DEMO and
  current live history/coding guards. Do not add guessed BMW mappings.
- [ ] A6: Pin only integrated dependencies; record actual license/notices and
  packaging closure. Inspect target Python 3.13 and source-checkout startup.
- [ ] A7: Perform doc 25's manual offline/capture verification; record evidence
  and limitations. Arrange an owner-operated read-only F48 validation, keeping
  hardware/platform acceptance pending until observed.
- [ ] A8: Run `scripts/preflight.sh` across the full app; open a new PR with
  ownership design, library dispositions, verification and remaining limitations.

No automated suite or `tests/`; no vehicle writes, DHCP changes or unsolicited
scanner runs. Missing BMW feature contracts belong to Task B, not invented
constants inside an adapter. Do not disable existing supported behavior merely
to make the migration appear successful; explain any candidate limitation.

## Required handoff to Task B

Record the final connection/service API, exact module paths and dependency
versions, target-address/session model, how operation contracts register codecs,
failure taxonomy, cancellation/recovery contract and local evidence locations.
Update docs 25/26 and `SESSION-PROMPT.md` after merge. Do not mark B complete
or imply F/G/U/I coverage from A's F48 validation.

## Verification record

Implementation plan/files: pending in the implementation session.
Offline/capture observations: pending. Vehicle observations: pending.
Ruff / formatting / mypy / packaging: pending for the implementation.
