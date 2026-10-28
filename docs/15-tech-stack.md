# Stack, networking and distribution status

Reviewed 2026-10-28. Replaces examples mixing asyncio, invalid discovery bytes,
privileged DHCP configuration and unverified packaging claims.

## Declared stack and observed environment

| Component | Declared/configured | Observed locally |
|-----------|---------------------|------------------|
| Python | 3.13 in CI, Ruff and mypy target | Venv reports **3.15.2** |
| PySide6 | 6.12.0 in requirements | 6.12.0 installed |
| PyInstaller | 6.22.3 in requirements | 6.22.3 installed |
| netifaces | 0.11.0 in requirements | 0.11.0 installed |
| PyCryptodome | 4.2.0 in requirements; supplies `Crypto.Cipher.AES` | 4.2.0 installed |
| mypy | Unpinned CI tool install | 2.4.0 installed |

Align the environment with CI before claiming reproducible packaging. The initial
audit changed no dependency pins. The PR review follow-up added the missing
PyCryptodome 4.2.0 declaration after a fresh CI install exposed it: an undeclared
AES import became Any under mypy and would be unavailable at runtime. This pin
matches the installed package used for app startup. See the
[official Crypto namespace installation guide](https://www.pycryptodome.org/src/installation)
and [release metadata](https://pypi.org/project/pycryptodome/4.2.0/).

Use Widgets, QSS, QThread/signals, sockets and SQLite. The app does not use asyncio.

Standard protocol reuse is implemented with udsoncan 1.26.1, Scapy 2.8.0 and
doipclient 1.2.2. Fresh Python 3.13.18 imports/type checks and a macOS arm64
bundle/startup were verified; Windows/Intel and hardware acceptance remain pending.
See [the integration record](../tasks/protocol-library-migration-verification.md) and
[the library evaluation](24-protocol-library-evaluation.md) for udsoncan,
doipclient and Scapy HSFZ, plus the Gallia alternative and adapter requirements.

## Network contract

Diagnostics use ordinary UDP/TCP sockets. Identify the wired adapter, physical
link, IPv4/netmask and route. An `enX` name, MAC or assigned IP does not prove
connected Ethernet. Scope both discovery and TCP to the selected adapter.

HSFZ uses UDP 6811/TCP 6801; DoIP UDP/TCP 13400 with routing activation. Chassis
selection alone does not prove transport support. Preserve discovered identity.

Do not force host IP `169.254.1.1`: it may already belong to the car. Do not
allocate DHCP leases from `169.254/16`; RFC 3927 section 1.6 reserves it for
link-local configuration rather than DHCP assignment. See
[IPv4 link-local specification](https://datatracker.ietf.org/doc/html/rfc3927#section-1.6).

DHCP fallback is **not validated**. Windows currently writes configuration and
returns false. macOS lacks a verified managed lifecycle. Network-configuration
UX is pending. Audit commands must not start DHCP, alter addresses, overwrite
system configuration or stop unrelated services.

An approved managed fallback needs an isolated non-link-local subnet, adapter
binding, conflict handling, elevation UX, coexistence, owned-process cleanup and
restoration of prior configuration. Global `killall bootpd` is not owned cleanup.

## Distribution

The macOS `--onedir` and Windows `--onefile` commands in `README.md` and
`AGENTS.md` are examples, not verified release builds. Use **BMW Self Service**
consistently. Resolve assets independently of working directory; user data
belongs in writable OS locations. Exclude research, sources and `.agents/`.

Release validation needs clean installs, complete assets/dependencies, demo
flows, launch outside the checkout, macOS Apple Silicon/Intel and Windows x64,
signing/notarization and persistent recovery data. Measure bundle sizes.

Normal diagnostic/coding/history workflows must work offline. Web search,
updates and redistribution of extracted data remain separate release decisions.
A created executable or a demo does not prove production readiness.
