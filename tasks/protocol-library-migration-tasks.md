# Task A — development tasks

Status: planned, 2026-10-28. All implementation/acceptance boxes are open.
Specification: [doc 25](../docs/25-library-migration-spec.md).
Design, exact paths, APIs and candidate gates: [implementation plan](protocol-library-migration.md).

The planning session completed the baseline caller inventory and design. A1
still requires implementing and verifying that design on a fresh branch from
current main after the planning branch merges. Check a box only with actual
implementation/verification evidence; reference-library behavior is not app proof.

## A1 — contracts, single owner and operation context

Depends on: merged planning documents and a clean, current implementation base.
Files: new `app/protocol/__init__.py`, `contracts.py`, `owner.py`;
`app/connection.py`, `app/worker.py`.

- [ ] Recheck the plan's caller map, native/result signals and import graph;
  record any changes before dependent work.
- [ ] Define DiscoveryResult, ConnectionConfig, EcuIdentity/EcuSession,
  OperationContext, TransportAdapter and immutable response/failure types.
- [ ] Implement ProtocolOwner's queue and ProtocolWorker(CarWorker) executor;
  keep sockets, receive stream, clients and session state on that one worker.
- [ ] Implement submission-time deadline, cancellation Event and generation;
  multi-request operations share one context, and expired queued work sends nothing.
- [ ] Define bounded polling, outstanding-request reconciliation/invalidation,
  asynchronous close and completion of waiting callers without GUI lock waits.
- [ ] Define result_ready versus native QThread lifecycle and the coherent
  consumer migration for A5; do not partially switch existing signal semantics.

Done when: manually trace queue/cancel/close/reconnect through one owner;
prove no backend I/O is reachable from GUI entry points in this slice. Keep the
new path unwired until service/adapters and A5 integration are ready.

## A2 — udsoncan bridge and standard services

Depends on: A1 contracts/ownership.
Files: new `app/protocol/udsoncan_connection.py`; `app/uds.py`,
`app/protocol/owner.py`, `requirements.txt`, library evidence manifest.

- [ ] Revalidate udsoncan 1.26.1 wheel/source identities against the retained
  manifest and pin it with its usable integration.
- [ ] Implement BaseConnection lifecycle/send/receive over raw adapter methods;
  do not wrap the existing blocking send_uds transaction.
- [ ] Resolve U-01/U-02: safe empty_rxqueue semantics and outer budget across
  queue/send/ACK/receive, with bounded library pending/session timing.
- [ ] Add typed session, DID read, DTC read/clear and TesterPresent services;
  preserve raw responses, status masks and checked service echoes.
- [ ] Keep mutable client/config/session state per ECU and owner-confined;
  enable negative/invalid/unexpected exceptions and map them to project failures.
- [ ] Expose immutable, identity/version-keyed codec configuration for Task B
  and an evidenced VIN codec; no mutable global or invented BMW codec registry.
- [ ] Resolve U-03 for existing legacy/raw requests. Document extensions versus
  unsupported operations without introducing a second pending/NRC dispatcher.
- [ ] Specify compatibility return/exception behavior, including final negative
  raw replies for unmigrated consumers, and keep those outcomes classified failed.
- [ ] Enforce the existing read-only bytes/subfunctions at the final send,
  including internal/client-generated requests and generic APIs.

Done when: manual byte inspection demonstrates standard request/response,
echo rejection, final negative and bounded pending behavior through the bridge;
policy blocks mutation bytes before transport. No BMW codec is invented.

## A3 — Scapy HSFZ adapter

Depends on: A2 bridge; source feasibility may be inspected earlier.
Files: new `app/protocol/hsfz.py`; owner/facade integration,
`requirements.txt`, library manifest and verification record.

- [ ] Confirm Scapy 2.8.0 source hashes; disposition H-01–H-04 individually
  with exact method and adaptation before selecting it for live traffic.
- [ ] Reuse Scapy HSFZ framing/stream support with selected-source TCP binding,
  bounded connect/read/write and explicit zero/failed-send handling.
- [ ] Implement selected-interface discovery preserving validated identity;
  bound declared lengths and retain partial/coalesced frames and controls.
- [ ] Dispatch addressed diagnostics separately from ACK/alive/errors; keep
  udsoncan as the only UDS interpreter and preserve raw transport capture.
- [ ] Compare session/VIN request/response bytes with doc 23's retained capture;
  record synthetic cases separately from those actually observed there.
- [ ] Manually exercise wrong endpoint, short control/header/body, oversized
  body, EOF, timeout/cancel, late response and incoming control traffic.
- [ ] Pin Scapy only with a usable bounded adapter. If small adaptation cannot
  satisfy the contract, document candidate rejection/upstream alternative and
  leave cutover pending rather than retaining two complete stacks.

Done when: HSFZ meets all candidate gates without root/pcap/scanner use or a
copied full transport stack, and no existing framing/transaction guarantee is lost.

## A4 — doipclient adapter

Depends on: A2/A3 contract established; source feasibility may be inspected earlier.
Files: new `app/protocol/doip.py`; owner/facade integration,
`requirements.txt`, library manifest and verification record.

- [ ] Confirm doipclient 1.2.2 identities; disposition D-01–D-06 individually.
- [ ] Bind discovery/TCP to selection and validate entity/VIN/address metadata;
  activate routing before diagnostic send with a bounded response check.
- [ ] Disable reconnect/resend paths and demonstrate no request replay.
- [ ] Cap every actual send/receive/ACK wait by the monotonic context, including
  unrelated diagnostic traffic; wall-clock timers cannot extend the operation.
- [ ] Retain diagnostics arriving before ACK; handle NACK and alive traffic
  during active operations and idle service without an extra socket reader.
- [ ] Select each ECU under owner serialization with full DoIP address width;
  do not use the stock fixed-target connector as a multi-ECU solution.
- [ ] Preserve raw fragments/control frames and stale-response ownership.
- [ ] Perform declared manual offline cases and pin only the usable backend;
  record upstream/alternative disposition if required changes exceed a small adapter.

Done when: each source-observed boundary has evidence, not only configuration;
DoIP hardware coverage stays unvalidated until separately observed. Gallia or
asyncio adoption requires a revised design and is not implicitly authorized.

## A5 — migrate callers, DEMO and lifecycle; remove duplication

Depends on: A1–A4 candidate gates; no GUI cutover before their integration is ready.
Files: `app/connection.py`, `app/worker.py`, `app/uds.py`,
`app/mock_connection.py`, `ui/main_window.py`, `ui/diagnostics_page.py`;
remaining compatibility consumers listed in the plan as necessary.

- [ ] Replace series-based transport assumption/HSFZ-only discovery plumbing
  with validated explicit transport identity; retain the current picker.
- [ ] Integrate setup's shared deadline and typed session/VIN validation;
  optional failures remain per-field and do not disconnect a verified car.
- [ ] Route post-connect and diagnostic workers through run_operation contexts;
  preserve explicit per-ECU coverage and meaningful failure results.
- [ ] Move keepalive/idle control service into the owner; remove competing
  KeepAliveWorker reads and document active ECU/session timing profiles.
- [ ] Remove the legacy GUI single-clear send route under D-16. Leave Task B's
  all-ECU coverage/Clear All/readback feature implementation explicitly pending.
- [ ] Replace GUI disconnect/late-result cleanup with asynchronous close;
  propagate worker interruption into contexts and ignore stale generation signals.
- [ ] Switch all CarWorker result consumers to result_ready together, restoring
  native QThread finished() for lifecycle completion and worker retention/reaping.
- [ ] Adapt DEMO without sockets/background live traffic; preserve fixture
  separation and distinguish synthetic timing/data from vehicle support.
- [ ] Audit security/coding/history/VehiclePage callers for bypasses; preserve
  disabled live history/coding guards and never activate old guessed requests.
- [ ] Remove app/uds framing/parsing and both superseded transaction loops once
  replaced. Account for every send_uds consumer as migrated, temporary compatible
  or explicitly inactive; do not leave an independently active legacy stack.

Done when: manual DEMO/visual checks and caller search show one live owner,
no GUI-thread network/lock waits, no stale results and no unsafe feature enablement.

## A6 — dependency, runtime, notices and packaging closure

Depends on: selected integrated backends and A5 import graph.
Files: `requirements.txt`, library manifest, `THIRD_PARTY_NOTICES.md`,
`licenses/`, docs 15/24/25; `README.md`/`AGENTS.md` packaging commands if needed.

- [ ] Finalize exact pins/hashes for integrated packages only; avoid unused
  Gallia/CAN/ISO-TP/raw-capture extras and broad startup imports.
- [ ] Use a fresh Python 3.13 environment for dependency installation, imports
  and app startup; record actual interpreter/package versions separately from
  the existing Python 3.15.2 venv.
- [ ] Record third-party license texts/notices and source-material obligations;
  obtain the owner's exact app-license choice before distribution.
- [ ] Verify dynamic Scapy/udsoncan imports and notice/resource collection in
  macOS/Windows bundles, then launch outside the checkout without research trees,
  admin privileges, pcap/Npcap or network access beyond ENET.
- [ ] Record bundle size, platform/architecture, source revision and actual
  results; macOS arm64/Intel and Windows x64 each need their own status.
- [ ] Record existing CI pip-audit outcome for the dependency changes and fix
  actual closure issues without weakening checks.

Done when: target runtime/import/closure evidence is recorded; unavailable
platform checks remain open and release/license gaps are explicit.

## A7 — manual acceptance and owner read-only validation

Depends on: integrated A5/A6 implementation. Inspect bytes during A2–A4 as well.
Files: new `tasks/protocol-library-migration-verification.md`, sanitized
`docs/evidence/` records, docs 24/25 as evidence changes.

- [ ] Complete every boundary/case in the plan's verification matrix, retaining
  context, exact expected/observed bytes or outcomes and limitations.
- [ ] Distinguish recorded HSFZ evidence, synthesized offline cases, source
  inspection, DEMO/visual results and new physical observations.
- [ ] Verify before-send cancellation/policy send nothing; after-send timeout,
  cancellation/loss retain ownership/uncertainty and never automatically replay.
- [ ] Verify queue/session/pending/fragment/control traffic cannot extend the
  operation budget and shutdown settles owner, queued callers and UI workers.
- [ ] Perform an owner-operated F48 `--debug --read-only` session to reestablish
  discovery/session/VIN, preserving explicit unavailable fields and partial DTC
  coverage. Retain raw logs locally with hash and sanitized shared observations.
- [ ] Leave F48 validation pending until the owner run is observed; separately
  record missing DoIP hardware and platform acceptance. No vehicle writes,
  privileged network setup, scanner or automated suite is part of this task.

Done when: implementation/offline, physical and platform acceptance are recorded
honestly. Pending required acceptance keeps Task A open.

## A8 — full gate, review and Task B handoff

Depends on: A1–A7 dispositions; incomplete acceptance remains visible in the PR.
Files: task/verification records, docs 15/24/25/26, `SESSION-PROMPT.md`.

- [ ] Review final ownership, candidate dispositions, deadline/cancel/policy
  invariants and complete caller inventory against spec 25.
- [ ] Run full `scripts/preflight.sh`; record Ruff lint, Ruff formatting and
  mypy separately and rerun all three after any fixes. Do not create `tests/`.
- [ ] Rebase/integrate current main as needed and repeat affected validation;
  keep meaningful reviewable commits referencing spec 25.
- [ ] Before every push or gh pr operation, use
  `gh auth switch --user lennoncarvalho`; open the implementation's own PR.
  Include selected/rejected candidates, API/ownership design, evidence and
  pending runtime/hardware/platform/license items. Never merge without instruction.
- [ ] Publish Task B's exact module/API/versions, operation/codec registration
  pattern, address/session model, outcomes, cancellation/recovery contract and
  evidence locations. Document any temporary compatibility callers.
- [ ] After merge, update handoff/status docs to the merged API and revision;
  do not mark Task A accepted while required validation is open or imply Task B
  is functional because the libraries are integrated.

Done when: reviewable implementation delivered with green full static gates,
accurate acceptance status and a concrete Task B integration handoff.
