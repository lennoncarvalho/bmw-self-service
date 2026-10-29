# PR13 review follow-up

Review baseline: daf7e55, PR13 open/unmerged. Scope: verify all Robin and
CodeRabbit inline findings plus the three Robin review-body findings. Fix valid
current-slice defects; specify larger Task B work for the next coding session.
No vehicle operations, source-recovery expansion or merge in this follow-up.

Plan: retire unused runtime legacy-file codecs to development tooling; restore
fixed connection guidance; settle coding UI/tab states; correct history service
choices/write guards and stale docs; review remaining findings against actual
contracts; perform offline/UI checks and full preflight before push.

Detailed dispositions and verification follow below.

## Robin inline dispositions

| Comment database ID | Finding | Verified disposition |
|---|---|---|
| 4414667410 | `_deadline` absent before `do_work` | Defensive fix: initialize0.0; premature private reads now fail with bounded TimeoutError. Normal worker lifecycle already assigned it before every read. |
| 4414667445 | request/context API may be absent | No defect in current callers: both live facades implement Task A API; DEMO bypasses these workers. Do not introduce guessed fallback APIs or redundant hasattr branches. |
| 4414667457 | Unbounded backup allocation | Incorrect: `read(MAX_BYTES+1)` already caps input at32MiB+1 and rejects excess. No streaming dependency added. |
| 4414667465 | Deep revision equality/key order | Use the validated full-record sha256 to compare revisions. Python dict equality already ignores key order; load/validation remain bounded linear work. Never compare original-only hash, which omits later events. |
| 4414667477 | Historical protection helper misleading | Removed unused family set/is_protected helper; no callers. Do not return false to imply authorization is unnecessary. Future writes require exact source contracts. |
| 4414667492 | AES key is256bits | Incorrect:32hex digits decode to16bytes; AES-128 comment and key stay unchanged. |
| 4414667510 | MIL unavailability reason hidden | Existing shared labels already display detail; added explicit transport-not-yet-implemented reason. Broader matching is next-session work, not a guessed universal DID. |
| 4414667523 | Discovery misses late replies without0.2s settle | Incorrect: current loop collects the entire bounded5s discovery window. Reintroducing early settle would shorten collection and weaken D-21. |
| 4414667542 | Permanent faults excluded from Clear All | Current behavior correct; clarified confirmation that only supported Fault/Information memories are cleared and Permanent is excluded. |
| 4414667559 | Duplicate message ambiguous | Now explicitly says known local records; car history unknown. Encoder docs corrected to local journal/intent rather than retired complete-car baseline. |
| 4414667577 | Private coding-reader access in guard | Added CodingPage.is_reading(); mutation guard uses public state. |
| 4414667596 | Rewrite reverse F101 parser forward | Rejected suggested offset8: source contract reads role records from response tail, including reverse ordering. A readability change cannot change byte selection/order. Offline variable-prefix check retained. |
| 4414667614 | Directory fsync cost | Documented directory-entry durability requirement. Not configurable away before live mutations. |
| 4414667633 | Catch BaseException | Reviewer explicitly says no change; standard Exception handling retained. |
| 4414667651 | Verify permanent layouts | Verified standard availability-byte and source legacy no-mask layouts, empty/one/multiple records and malformed alignment. No decoder change required. |

## CodeRabbit inline dispositions

| Comment database ID | Finding | Resolution |
|---|---|---|
| 4414857518 | Legacy file codecs in runtime | Moved unchanged helpers to development-only scripts/inspect_history_format.py. No runtime imports/callers; ADD/result helpers remain in app. Source-format evidence remains in deep-investigation docs. |
| 4414857543 | Connection setup guidance lost | Map known ConnectionError prefixes back to fixed cable/ignition/IPv4/interface guidance. Unknown exceptions remain generic; no arbitrary exception text exposed. Read-only not-found dialog remains reachable. |
| 4414857560 | Retired reader/draft directions | Corrected recovered-contracts remaining work to local JSON/journal/append/replacement and D-57 incremental owner merge. Three-variant MIL status updated; broader recovery remains required. |
| 4414857574 | Advanced loading and tab mismatch | Settle both coding pages after result/error; Advanced shows unavailable rather than reading forever, and Easy button matches selected page0. Existing stale-connection guards remain. |

## Robin review-body findings

1. History write stub: live buttons were already disabled, but handler could
   still launch a refusing worker if reached. All write-enable callbacks now stay
   disabled and the handler performs no send/worker launch. UI explains that the
   local JSON and journal-backed append/replacement implementation is pending,
   rather than promising a reader. Future B5 work remains explicitly queued.
2. Legacy coding manifest: only DEMO could reach that path; live snapshots already
   use OperationStore. Renamed/guarded it as `_save_demo_preview`, marked the
   metadata non-restorable and isolated it under BMW-Tool/demo-previews. Do not
   fabricate ECU baseline blocks from UI categories. Full B6 write integration
   remains in next-session tasks and uses OperationStore with real ECU bytes.
3. Service choices: centralized all14 evidenced decimal IDs/English labels in
   SERVICE_TYPES and reused them in the form; removed duplicate Oilfilter and
   invented coolant/transmission entries. New ADD encoding rejects unlisted
   service codes. Legacy research round-trips still preserve original raw data.

## Verification boundaries

No vehicle traffic or new write capability. No automated suite created. Manual
one-off/offscreen byte and widget checks plus full preflight are recorded after
execution below. Source-derived breadth/history/coding implementation continues
on a fresh origin/main branch only after the owner merges PR13 (D-57).

Executed verification: all14 source codes accepted; unsupported18/35 and local
same-day duplicate rejected; moved research codecs round-trip the original
8-record sample byte-for-byte; runtime API no longer exposes those codecs.
Permanent-memory empty/one/two-record layouts and malformed alignment, variable-
prefix tail F101 decoding, pre-run deadline rejection, fixed setup messages,
oversize backup rejection and full-revision import conflict handling passed.
One initially invalid negative fixture was actually a valid standard permanent
record and was corrected before the full successful rerun; no decoder was changed
for that fixture.

Offscreen checks passed for snapshot failure settling both tabs, correct Easy
selection, live rejection of DEMO-preview persistence, fourteen form choices/
thirteen-item selection limit and a history write handler that launches no worker.
Independent review also exercised actual background error signal delivery, DEMO
preview path/metadata isolation and encoder boundaries; no blocking findings.
Full Ruff check, Ruff format check and mypy pass over all33 app/UI/main modules.
The new development script also passes Ruff check/format independently.
No car traffic, hardware validation, packaging, Python3.13 run or full Task B
completion is claimed. Local runtime remains3.15.2.
