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
