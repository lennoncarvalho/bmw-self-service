# Protocol dependency notices

The protocol migration incorporates these exact releases. Their unmodified
license texts are in `licenses/` and must accompany distributed bundles.

| Distribution | Release | License | Scope used |
|--------------|---------|---------|------------|
| udsoncan | 1.26.1 | MIT | Standard service client/codecs, response checks and pending timing |
| Scapy | 2.8.0 | GPL-2.0-only | HSFZ packet definitions and serialization; no capture drivers/scanners |
| doipclient | 1.2.2 | MIT | Released Parser/message types and packet serialization |

Wheel identities/source hashes are recorded in
`docs/evidence/protocol-library-inventory.json`. Source wheels and their PyPI
source distribution links remain available from the exact release pages listed
there. Release preparation must provide the corresponding GPL source and build
materials by a compliant distribution method, alongside the application source.
The owner's acceptance of GPL-compatible distribution does not select the app's
exact license. That choice and complete release source materials remain a
release gate; a local development build is not distribution approval.

These notices cover the newly selected protocol libraries. Existing Qt,
PyInstaller, networking, crypto and data-asset distribution obligations also
remain part of the release review described in docs/15-tech-stack.md.

## Job interpreter (native)

| Component | Source | License | Scope used |
|-----------|--------|---------|------------|
| ediabasx-native | `github.com/emdzej/ediabasx` commit `78a3f5f407a2fb0e2561c61b83a8dd560f3e4214`, `native/` C11 port | PolyForm Noncommercial 1.0.0 (`native/ediabasx/LICENSE`) | BEST/2 interpreter, PRG/GRP parser, POSIX file loaders; built into `native/build/libedx` with `native/edx_shim.c` |

Vendored into `native/ediabasx/` without the TypeScript packages, tests, CMake
files or the POSIX serial transport. The vendored files are unmodified.

PolyForm Noncommercial permits personal, noncommercial use only. This is acceptable
under D-63 (personal use, no public or commercial release). Any public or commercial
distribution of a build that includes this library needs a different license from
the licensor first.
