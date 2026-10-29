# Broad ENET topology selection recovery

2026-10-29. **Primary implementation reference**, recovered statically with
REA/JADX 0.7.1. These observations do not establish vehicle execution or fleet
validation. No reference application was launched and no car request was sent.

## Inputs and retained evidence

- S-01 diagnostics APK 2.36.1-6731, SHA-256
  `da6f5b39efaa590fce68782f439c1b8f1b9f09ed41344055b8ff80666cae00d5`.
- S-02 coding APK 4.25.04-12743, SHA-256
  `fc6eedeb741cbec49f46c126f8c72dac6a3dd1455f8a993c028695642459b728`.
- Local portable bundle:
  `/Users/lennon/BMW-Tool/investigations/task-b-topology-selection-evidence.json`,
  216,874 bytes / 21 records, SHA-256
  `cc08ef90e2c92811cc920b69f2cedba042a354504e54b3b7657a1b694ccbaf57`.
  It contains original artifact identities, complete
  method observations and tool identity. It is development evidence, not an app
  dependency. Additional recovered methods and limitations below identify the
  complete selection chain; existing PR13 inventory/F150 contracts are reused.

## Missing source branch: catalogue-derived discovery candidates

The source does **not** stop discovery after the gateway inventory request fails.

| Source method | Complete source behavior | REA Evidence |
|---|---|---|
| `j6.g0.j.a(Exception)` | If not cancelled, replace target list with `j6.g.b(Boolean.valueOf(L()))`, then continue identification | `ev_8ae637ca80932c94041689d37c83361d9c4f1dd98a142408335ac4716d99ae9b` |
| `j6.g0.j.b(ArrayList)` | Start with gateway targets; if empty or `extended_scan` preference is true, use the same catalogue-derived list | `ev_f8732ea980e8c2b7b03d4a0bf74c9f2c7a8c2b91aa80bc744f7f74d4d0a5705c` |
| `j6.v.L()` | Return true, selecting UDS rows for the F/G interface | `ev_b68097a97754340bed91eae49fadf2f14c5af588cd442fd97f43829de0abaa83` |
| `j6.g.c(Boolean)` | Load all `h.c()` catalogue rows, require `h.p()==requested UDS flag`, deduplicate address objects, sort | `ev_f368b6d8fc5feb2835700055a5a821ff23ba8fcb6951f7747c537add2ba2fb95` |
| `j6.g.b(Boolean)` | Convert the selected address objects to integer addresses | `ev_18d52d47fc01f0b33bd5d9212d2d89b036974a606574163d152861f71fecf5be` |
| `j6.g0.R()` | Visit each address in sequence and call `O(byte, callback)` (the recovered F150 identification operation) | `ev_36c12667b88e7a946af96062de8725a3d4ea6769effa22192ded5b6b27880d85` |
| `j6.g0.b.a(Exception)` | Continue to next address on failed identification | `ev_bf3816d1af7ca76f49dd9dc7c482fa67882f5fbc7fdf8a694cacc207ad50b7ce` |
| `j6.g0.b.b(h)` | Accumulate identified exact catalogue row, then continue | `ev_bb30a4069caefc9328350645d5fbf63084b1439f458a2febbb7412d14e877a4c` |

The existing deterministic diagnostic catalogue has 1,307 exact rows, including
691 UDS rows covering **148 distinct byte addresses**. This was calculated
offline from all `variants` rows in `coding_data/diagnostic_catalog.json.gz`, not
from the owner's F48 or a small chosen list. Address `00` is present as an actual
catalogue address; this does not authorize coercing an unknown address to zero.
The other 616 non-UDS rows are outside this source branch. There is no KWP
fallback in this F/G identification chain.

All 148 addresses lie between `00` and `B6`; tester `F4` and functional `DF`/`FF`
are absent from the filtered catalogue. The source's `g.equals` deduplicates
solely by integer address and `g.b.a` compares integer addresses numerically.
`v.O` has an optional `skip_headunit` preference defaulting to false; it can skip
`63` when explicitly enabled. Neither selector excludes the catalogue's genuine
address00 or adds tester/functional addresses. These details were corroborated
against retained extracted smali; the REA selector/method observations above
establish the shipped-artifact chain.

The source's broad scan supplies **candidates**, not proof that 148 ECUs exist.
Integration must preserve the gateway-inventory failure, candidate provenance,
individual identification rejection/unavailable/unattempted outcomes and overall
coverage. Exact unknown variant replies are still observations even without a
matching description definition. Catalogue absence is not vehicle absence.

The source continues after any callback error. Our existing protocol owner must
retain its stricter stream-ownership rule: continue only while the stream is
healthy, never after an ambiguous timeout/tainted exchange. The existing bounded
overall operation deadline still applies; exhausted candidates are unattempted,
not silently omitted or reported as absent. This branch requires no diagnostic
write or change to session ownership.

## ENET selection and host configuration

S-02 `c.a.a.a(Context,String)` maps `enet_cable` directly to `c.a.m` (ENETAdapter).
The complete factory observation is
`ev_2444ff27f888ad2cee53a355878b543517661154a414ec29499202827dde76c0`.
Excluded Wi-Fi/Bluetooth/USB choices are separate factory branches; they do not
belong to the app's cable-only scope.

`c.a.m.p(...)` enumerates existing interface broadcast addresses, excludes
loopback broadcasts, appends `169.254.255.255` and `255.255.255.255`, then tries
the ENET connect task. It contains no DHCP server or IP-address reconfiguration:
`ev_e8475ac0b4a2968d38e06e8049552201ff60c3f58532d68c36ff0292bb3475a8`.
`c.a.n.doInBackground(Object[])` sends `00 00 00 00 00 11` to UDP6811,
receives a datagram and connects to that sender on TCP6801:
`ev_e1d3f790c87d234ab732b7195cbf6b022c3013226f686a6b22f557c76199eb35`.
This is an HSFZ contract. Retain this app's stronger selected-interface scoping,
response validation and full-window multiple-vehicle refusal instead of copying
the reference's first-response acceptance or broadcasts over every interface.

D-24 assessment: this recovered reference path operates on existing host
network configuration and gives no reason to enable automatic privileged DHCP
fallback. It does not prove that every macOS adapter is configured or linked;
native adapter identity/link/address inspection remains platform work.

## F/G interface branches and coding selection restrictions

`ConnectCarActivity.A0()` selects interface `t0` for category3 and `s0` for
category2, independently from the ENET adapter factory:
`ev_b0992eebbfe32ec16ba6b768d797af22e97246c2958d288d9f72949f27249e07`.
`t0` is GSeriesVehicleInterface and extends `s0` FSeriesVehicleInterface.
Its complete declared member inventory contains only constructor and `z`:
`ev_08d79dc4bb62c0e5def864b50d10d3475c3a7b892c4780176620b5c5ba59be4e`.
Consequently its inherited F150/inventory readers use the same byte-addressed
HSFZ path. `s0.T(byte,r)` sends `22 F1 50`:
`ev_3836eaa7d4d2ab5ab75c29cc2f8f16d0d2aec3c4a6bcddc2078ae7040219b87b`.

The sole G override `t0.z` sends a body-controller routine, unlike `s0.z`.
These are **mutation routines**, not discovery/session prerequisites to add to
connection. Their observations are retained only to prevent misclassifying the
G override as transport selection:
`ev_a1b8e1c8417579c9142de72ebb7c87f7627608ced970ad4ae037aa0338198181`
and `ev_e297bf902ddec1391ed17343decfa240ca38b4d2ddc77f3dbd4748c44b9cbe82`.

Coding's `s0.p.b(String)` excludes address18 unless its F150 variant is exactly
`0F14B0`, `0F14B8` or `0F21D0`, before invoking F101 selection:
`ev_eaeadf0b396d34aaaa5d76a9ff0686072cb235d49981d62178f822e6be1ba764`.
This restriction applies to that coding-source path. It must not become a
diagnostic discovery exclusion. Existing complete tail-based F101 decoding and
exact definition matching remain required.

## Concrete remaining branches

- No full-width DoIP inventory-to-logical-address mapping was established by
  these observations. The direct ENET factory and inherited F/G reader chain
  recovered here use HSFZ; do not invent an address-prefix transformation.
  Further mapping work must identify a supplied PRG/transport implementation
  with an actual logical-address conversion. `ediabasx/packages/protocol-doip`
  is only a placeholder and supplies no such contract.
- Explicit U/I model/category mapping in supplied vehicle metadata and newer
  transport branches remain source work. Inherited G readers do not imply all
  present/future chassis or ECU software has the same contract.
- `s0.t` supplies vehicle order through gateway `22 3F 06`, not FA XML. `b1`
  parses a bit-packed six-bit-character structure. These methods were retained
  as a next dashboard/configuration lead; the complete bounds, section markers,
  field names, sentinels and model lookup still need tracing before enablement.
- Source support, implemented behavior, offline checks and physical observations
  must remain distinct in the increment's final verification record.
