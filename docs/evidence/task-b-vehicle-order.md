# Packed gateway vehicle order

2026-10-29. **Primary implementation reference**, S-02 coding APK
4.25.04-12743, SHA-256
`fc6eedeb741cbec49f46c126f8c72dac6a3dd1455f8a993c028695642459b728`.
Static REA/JADX0.7.1 observations; no app/car execution or physical acceptance.

Retained bundle:
`/Users/lennon/BMW-Tool/investigations/task-b-vehicle-order-evidence.json`,
217104bytes,30records, SHA-256
`f12be8538148adace60f4753d94e617fb4319b052da7907d1ff7c06754868ca7`.
The full records preserve source text, exact DEX prototypes/provider/artifact
identity and explicit decompiler limitations. Names below are under
`de.appomotive.bimmercode`.

| Recovered method | Contract / Evidence |
|---|---|
| `models.s0.t(a1.f)` | HSFZ gateway10, `22 3F 06`; `ev_752b8e67ea92e02cce636900caa914acd104d5636a5a10eb00bc2b63c0666b4d` |
| `models.s0.b.b(c.b.d)` | Reject negative/non62; pass PDU bytes starting at5 to b1. Prefix bytes3–4 are skipped without interpreting them; `ev_404715f3b263f9e3bac58fbebbd5899b9ea27da6ed09045f75f514c04b7b9089` |
| `models.b1.<init>(byte[])` | Version byte0, fixed4-character fields at bits8/32/56/80/104. Optional ordered tags8/4/12 at bit128 and following terminators; `ev_8335b64030562da2993a98e1331d0c96136d0f6792cbd579554d270af38c73f7` |
| `models.b1.b(byte[],int,int,Boolean)` | MSB-first6bits per character; optional item stops if first2bits00. Item widths3/4/4characters. Terminator consumes2bits; next section tag consumes4bits; `ev_b4286d4aafcda560d2d2b0a5d71d5bbc096df51714e5089bdc3bf4b68f64ec33` |
| `models.b1.a(StringBuilder,int)` | Map low6bits: group00→0+low4,01→48+low4,10→64+low4,11→80+low4. Runtime rejects control characters, instead of displaying them; `ev_6082d2b543317b5be650b725068b59b48b820447184023e6126daf8a605e7ded` |
| `models.b1.c(byte[],int,int,Boolean)` | MSB-first section-tag bits; `ev_db066b5c44a9b0e196896c1b7ad11be1a60060d83b0a3b3ae038e4f052be531b` |
| `a.g0.<init>(Context,b1,w0)` | UI labels getters g/h/i/e/j as model range/time criterion/type key/paint/upholstery; getterf supplies option-code list. `ev_8615a17f7ae2620c35ff3bc7a594396f611e7e21f43e776e0092f050493585f7` |

## Standalone interpretation and bounds

`app/vehicle_order.py` checks exact62/3F06 echo,22–4096totalPDUbytes,
all bit/item bounds and known-section terminators. It preserves the complete
response and opaque framing prefix. Fixed fields are configuration codes;
time criterion is **not** an observed production date. Model range/type key
are **not** a decoded trim, powertrain, transport or write authorization.
No date/century/model is guessed. Unknown tags/nonzero trailing data mark
configuration decoding incomplete. Known truncated sections reject the result;
a partially decoded list is never silently presented as complete.

Tags4and12remain numbered codes because their semantics are not proven by the
reference's display. The source constructor appends both to the same internal
list; it exposes only tag8through getterf. Our decoder preserves these sections
separately and displays their numbered provenance, without inventing names.
Unknown raw bytes survive even where configuration decoding is incomplete.
No option codes, fields or interpretation are used to enable ECU writes.

The read is another task in the existing settled PostConnectWorker batch,
inside its30second operation scope. Definite optional-read failure leaves
vehicle order unavailable and does not disconnect a healthy session. A lost
stream is owned/inhibited by the existing protocol owner. DoIP sends zero
vehicle-order requests until the logical-address branch is recovered.
UI initial/refresh/reset replaces the complete configuration result. No FA XML
is synthesized. The old unused chassis-to-protocol mapping and misleading
model/year examples in the series picker are removed; discovery still decides
transport independently from the hint.
