# Task C implementation and verification

Branch: `codex/task-c-cbs-reliability`, based on the clean local main after
fetching origin on 2026-11-05. No PR is authorized.

## Plan

1. Reconcile the current CBS contract and all 48 definitions against the supplied
   reset orchestration, group routes and native PRG jobs. Retain an exact matrix
   for the eight observational branches and absent D94 dependencies.
2. Correct recovered selection/decoding in `app/cbs.py` and the generated contract
   compiler/assets, preserving native readers and exact mutation grants.
   The expanded native oracle found BCP_SP21 has 1,844 source tables; the native
   loader silently discards directories above 1,000. Correct the bounded table
   loader in `native/ediabasx/src/prg.c`, rebuild the standalone library and rerun
   the actual read/encoder oracles. This does not confer reset ownership on BCP.
3. Make `ui/cbs_panel.py` and `ui/main_window.py` retain settled results and
   visible errors, prevent competing foreground work and stale reset selections,
   and explain unsupported/read-only actions.
4. Correct reset preflight, single-owner execution, durable occurrence accounting
   and post-state presentation; preserve source refusals and uncertain outcomes.
   The real loopback owner exposed lost native transmission flags in nested
   callbacks. Correct `app/protocol/facade.py` so each child context records its
   actual send while inheriting the outer operation budget and cancellation;
   aggregate those facts back to the sole owner.
5. Exercise current native read/encoder oracles and one-off offline failure and
   Qt checks outside any test suite; review the diff in a separate pass, fix
   findings, run full preflight, and record precise physical acceptance limits.

Verification results, source findings and remaining exact branches follow here
as work completes. Physical operations require separate owner authorization;
this task does not perform a vehicle reset for testing.

## Implemented and verified

- `app/cbs.py`: strict native result accounting, calendar/count boundary fixes,
  source-defined reset items, unavailable/duplicate records, software retention,
  immutable worker confirmation copy, default-session checks, same-owner reset
  lifecycle and honest pending/refusal/error outcomes.
- `app/protocol/facade.py`: nested native callback contexts retain actual send
  flags and inherit the enclosing deadline/cancellation; outer mutation facts
  remain complete. Verified through the real owner, not only fake connections.
- `native/ediabasx/src/prg.c`: bounded complete table directories above 1,000;
  actual BCP_SP21 has 1,844. All 530 current assets load; three malformed
  directories are rejected. Universal arm64/x86_64 library rebuilt with zero
  compiler warnings under the existing `-Werror` build.
- Generated CBS contract/compiler/runtime asset: 48 rows, 47 current native
  readers, current software request and exact item identifiers; source roles
  remain distinct from encoder presence. Runtime manifest hashes updated.
- `ui/cbs_panel.py`, `ui/main_window.py`: exclusive foreground loading, retained
  stale rows and independent outcomes/errors, forecasts/status, stale selection
  rejection, clear read-only/DEMO/transport reasons, and post-uncertainty lockout.

The [evidence](../docs/evidence/task-c-cbs-reliability.md) and
[matrix](../docs/evidence/task-c-cbs-reliability.json) retain artifact identities,
all current branches/dependencies, exact oracle scope and the owner-F48 procedure.
No supplied CBS PRG has a missing USES dependency. D94 is absent, and eight
observations still lack established primary reset ownership. The motor
correction and delivery-module leads were traced without treating left-ECU
fault reads or CMEDIAR telephone operations as reset authority.

Observed offline: 1,034 native read vectors, 754 item encoders, 47 software
readers, 121 reset-worker scenarios, seven fragmented real-owner loopback
scenarios (including actual pending deadline exhaustion and session refusal),
additional zero-send guards, and actual Qt/DEMO flows. Native source file access
was denied during loopback execution. Full app Ruff lint, Ruff format check and
mypy pass over 52 files; the modified compiler's scoped Ruff checks also pass.
Local Python is 3.15.2, not the target 3.13. No test suite was introduced.

## Separate review pass and limits

The implementing assistant reviewed the final diff separately against the source
and failure paths. Fixes from that pass include preserving outcomes after a
failed refresh, preventing the overview/CBS post-reset refresh race, handling
default-session restoration, retaining the valid CBS7 count 250, rejecting
unknown routine result codes and preserving child/outer transmission facts.
Current native reader/encoder, actual-owner and Qt checks pass after these fixes.
This is not a second reviewer: independent human/agent review remains pending.

No physical vehicle request, gratuitous reset, Windows/package acceptance, push
or PR was performed. Physical acceptance is separate from implemented source
support; it does not require another vehicle to reproduce the retained checks.
