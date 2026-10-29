# PR15 review follow-up

2026-10-29. Scope: fix the three validated CodeRabbit findings on existing PR15,
`codex/task-b-vehicle-order`. The separate CBS documentation branch is unchanged.
No new PR is requested or created.

## Concrete plan

1. `app/vehicle_order.py`: accept the complete16-byte packed fixed payload
   (21-byte PDU); check remaining bits before each optional4-bit tag. Accept
   zero padding after terminated sections; retain unknown nonzero remainder as
   incomplete. Preserve bounds/known-item/terminator rejection.
2. `ui/vehicle_page.py` / `ui/main_window.py`: add order-specific invalidation
   and invoke it on fatal post-connect/refresh errors. Clear/collapse/disable
   old configuration while preserving MIL-only age invalidation semantics and
   stale-connection guards.
3. `docs/evidence/task-b-mil-breadth.md`: reconcile earlier source status with
   completed block tracing and remaining sequence ownership/cleanup/uncertainty/
   read-only enforcement. Update vehicle-order bound documentation.
4. One-off offline parser/Qt error-path checks, regression verification, full
   app Ruff lint/format/mypy, commit and push to the existing PR15 branch.

## Other reviewed comments

Robin infinite-loop claim: bounds-checked reads and monotonically increasing
positions already terminate malformed input. Decode-error claim: PostConnectWorker
already catches it and publishes unavailable. Cache claim: the catalogue is a
static bundled runtime asset, with no supported hot reload. No changes needed.

## Verification and result

All three CodeRabbit findings fixed. Decoder accepts the exact21-byte fixed
response and optional sections ending at EOF/short zero padding, without relaxing
known-item/terminator bounds. Nonzero unknown tails remain incomplete. Fatal
worker errors and results delivered after connection closure both clear old
configuration; ordinary MIL age invalidation and stale-session callbacks do not.
Earlier MIL block status now matches the completed source tracing.

One-off `/tmp/pr15-review-fix-check.py` passed: all8optional-section combinations
without an artificial trailing tag, empty8/4/12sections, fixed-only response,
unknown/nonzero tails, malformed/unterminated/truncated/oversized rejection and
actual MainWindow fatal/closed-result paths with a Qt VehiclePage. Verified
summary/details clearing, panel collapse/disable, refresh availability, age-only
and stale-connection guards. Earlier verification vectors appended an extra zero
tag and missed the minimal EOF case; this check corrects that coverage gap.
An initial nonzero-tail fixture accidentally encoded a valid empty8section;
it was corrected to an unknown tag before the successful run.

The prior full MainWindow/DEMO visual regression script passed again: background
DEMO connect, settled refresh, English/unknown labels, failed optional refresh,
mutation lockout and clean shutdown. Visually inspected the fixed fatal-error
page. Independent review found the additional closed-result path, now fixed;
final review recorded below. Full scripts/preflight.sh passed Ruff check,
Ruff format check and mypy35files. No tests/ suite or vehicle traffic.

Retained scripts/logs/screenshot:
`/Users/lennon/BMW-Tool/investigations/pr15-review-followup-20261029/`.

Final independent review: no remaining findings. Separate one-off script checked
216section-presence/count combinations, exact fixed EOF, short padding/unknown
tails/truncation and Qt current/stale/closed-result paths. Retained the script
alongside the parent verification artifacts. Full static gate rerun before push.
