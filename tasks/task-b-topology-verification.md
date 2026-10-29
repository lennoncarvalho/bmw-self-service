# Task B topology/dashboard increment verification — 2026-10-29

Branch codex/task-b-topology-selection, clean start from fetched origin/main
06e8baf after GitHub connector confirmed PR13 merged. No unrelated changes were
present; no commit was made to main or to the merged branch.

## Implemented outcome

- Source S-01's failed/empty gateway3F07 branch identifies all148distinct UDS
  catalogue addresses through F150. All691UDS mapping rows feed selection;
  there is no F48/year/chassis probe list. Successful gateway topology retains
  its original order/targets; unknown exact replies retain their raw variant.
- Every target retains origin, inventory state and identity disposition. Catalogue
  candidates are explicitly not installed/discovered topology. Diagnostics stays
  incomplete for these scans and names the gap before Clear All. Only positively
  identified supported ECUs can be used by subsequent reads/clears.
- One absolute30-second inventory budget includes catalogue loading and all
  queued identity exchanges. Negative responses can continue; lost/tainted
  streams and expiry leave later targets unattempted, with no retries/reconnect.
- Native QNetworkInterface Ethernet type/name replaces enX and interface-number
  guesses, excludes observed Wi-Fi/virtual interfaces, and revalidates the selected
  interface's single IPv4 at discovery. No guessed fallback names, subprocess,
  admin action or host network mutation. Labels describe IPv4 configuration,
  never prove link/car presence. Existing full-window discovery is retained.
- Generated exact MIL contracts account for all62engine identity rows/26names.
  53rows/17definitions select three traced scalar DIDs (4A69/50D8/42BC); remaining
  nine identities have explicit source/decoder dispositions. No family fallback,
  arbitrary truthiness or fault-count inference. Shared stale/unavailable states,
  initial settlement, bounded refresh and mutation lockout remain.
- Old ECU labels hide before deferred Qt deletion when a refreshed batch replaces
  them; this prevents stale repaint while preserving QObject lifecycle ownership.

Source identities, exact methods/jobs/coordinates, hashes and portable REA
exports: [topology source](../docs/evidence/task-b-topology-selection.md),
[MIL source](../docs/evidence/task-b-mil-breadth.md) and its JSON manifest.
The full original diagnostic catalogue/English descriptions are unchanged.
The new6359-byte coding_data/mil_contracts.json is explicitly tracked despite
coding_data's default ignore rule; normal resource lookup/packaging includes it.
The app requires no REA, PRG interpreter or reference executable at runtime.

## Executed offline checks

Temporary one-off scripts remain outside the repository; no suite/tests directory.

- All148catalogue addresses, exact counts/range and absence of tester/functional
  addresses; valid gateway list, malformed duplicate inventory, empty inventory
  and definite rejection; exact supported/unknown/negative F150 replies.
- Error/empty/invalid fallback returns148rows and149synthetic requests including
  gateway. Lost stream at first candidate leaves147explicitly unattempted.
  Already-closed connection sends nothing; DoIP sends no guessed byte probes.
  Shrinking request budgets and expiry produce no later sends.
- Actual DiagnosticReadWorker QThread lifecycle produces one settled444-memory
  outcome with topology_known=false, complete=false and no request to an
  unidentified candidate. No protocol owner/socket is replaced in app code.
- All62MIL identity branches:53exact source-selected requests, nine no-send
  dispositions. Three DIDs decode0/1; negative/wrong-DID/short/extended/2/255
  replies rejected. Missing/duplicate/unidentified/name mismatch send nothing.
  Generator reproduces asset and manifest byte-identically from original PRGs.
- Native host Qt inventory identifies en0 as Wi-Fi and omits it from Ethernet
  choices. Synthetic Wi-Fi, single-IPv4 Ethernet with arbitrary native name,
  multiple-IPv4 Ethernet, empty, loopback and unknown candidates exercise filtering/
  revalidation. No network traffic or host configuration was performed.
- In-memory UDP/socket/clock exercise retains both HSFZ/DoIP probes bound to the
  selected IPv4 and the entire5-second observation window. A second vehicle at
  4.9seconds is refused; same-IP conflicting VINs are refused; sockets close.

## Qt/DEMO and review

Offscreen QApplication with real MainWindow/ConnectWorker and DEMO data:
Ethernet picker, background connect, overview/Diagnostics render and shared MIL,
partial candidate origin/outcome visibility, mutation refresh/close lockout and
clean shutdown passed. Screenshots were visually inspected after settlement:
/tmp/task-b-topology-welcome.png, /tmp/task-b-topology-demo.png,
/tmp/task-b-topology-partial.png and /tmp/task-b-topology-demo-diagnostics.png.
An initial fixture referenced a nonexistent engine name; the fixture was corrected
and rerun. Visual inspection exposed stale deferred-delete labels; hide-before-
delete fixed that repaint and the corrected visual run passed.

Independent reviewer loaded Python/Qt/protocol guidance, reviewed diff/callers
and source manifests, independently reproduced the MIL asset/manifest, repeated
all62MIL selections and malformed replies, fallback/deadline/closed-stream and
native interface checks. No blocking findings. Delivery review noticed the ignored
new MIL asset; it is explicitly included in the commit. Diesel semantic labels
are retained in the reproducible source manifest. No owner-car request/write.

Full scripts/preflight.sh passes Ruff check, Ruff format --check and mypy over
all33app/UI/main modules. The research generator separately passes Ruff check
and formatting. git diff --check and changed-document local links pass.

## Remaining concrete work and verification limits

Task B remains incomplete. Continue source recovery for actual full-width DoIP
address translation, explicit U/I category/metadata, bit-packed3F06 vehicle-order/
model/configuration decoder, five older MIL block-reader chains, alternate
DME9FF_R/EDMEI1 MIL and missing DME98_R/FCCU definitions. Reconcile diagnostic
category/detail/description coverage, then implement local history JSON/cards/
journal, history append/replacement and complete applicable easy coding/recovery.
These are implementation/source tasks, not missing-hardware waiting states.

Local runtime is Python3.15.2; repository target remains3.13. No3.13execution,
physical car/lamp validation, diagnostic clear, history/coding write, restore,
reference executable launch, DHCP/network mutation, Windows run or packaging/
signing was performed. Only the owner's F48/NBT is available for physical checks;
this increment adds source support/offline verification, no new physical claim.

One-off checks, logs and all four screenshots are also retained under
/Users/lennon/BMW-Tool/investigations/task-b-topology-20261029/;
verification-files.json records each saved SHA-256. The original temporary
files are not the only retained verification record.
