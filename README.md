# BMW Self Service

Personal-use Python desktop app for BMW diagnostics, CBS, local service history
and coding over an ENET cable. Broad source-supported F/G/U/I coverage is the
goal; the current milestone is macOS source use with ISTA 4.29/HSFZ contracts.
Implementation and offline checks do not establish universal vehicle validation.

- [Plan](plan.md): wanted features and approved behavior.
- [Data guide](docs.md): source locations, recovered contracts and reproduction.
- [Tasks](tasks.md): current implementation steps, starting with CBS.
- [Contributor rules](AGENTS.md): workflow, safety and quality gate.

## Run

Use Python 3.13 and the existing project virtual environment/dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py
```

For Windows activation use `.venv\Scripts\activate`. Windows and packaged-release
acceptance are later work. Runtime databases/job assets must already be generated;
see [asset reproduction](docs.md#reproducing-assets). Launching the app never
requires reference applications, source folders or REA.

## Connect and inspect

Connect the ENET cable to the computer's Ethernet adapter and the vehicle's OBD
port, using the vehicle's appropriate ignition/diagnostic state. Launch read-only
for observation:

```sh
.venv/bin/python3 main.py --debug --read-only
```

Select the series hint and Ethernet adapter, then connect. Discovery and exact
ECU identities determine support; year/chassis alone do not. Optional read
failures remain visible without discarding a valid connection. Service status
requires the explicit **Read service status** action.

DEMO mode in the gear menu explores the UI with local fixtures and does not
validate car behavior. Writes require the feature's exact source-backed gates,
confirmation and durable state. History shows local records; it cannot read or
back up the existing car history. Replacement irreversibly removes omitted
entries. No operation is automatically replayed after an uncertain outcome.

Session logs go in `logs/` inside the app root, independently of the launch
directory, with `~/BMW-Tool/logs` as a reported fallback if that location is
unavailable. If neither location works, startup continues with console logging.
The log directory and files use owner-only permissions, including rotated segments.
Files always retain DEBUG request/reply details; `--debug` also shows
them on the console, and `--no-log` disables file logging. Each session retains
up to six 10 MiB segments; include rotated segments when sharing a large session.
Logs contain full vehicle identifiers. Existing `~/BMW-Tool/logs` files are preserved.

`~/BMW-Tool/cbs` stores reset intent/results, `backups` stores coding baselines
and outcomes, and `history` stores local projects and write journals. These are
durable operation data; keep them until explicitly deleted. `investigations`
contains development research only and is never read or created by the running app.

## Development

```sh
scripts/preflight.sh          # full Ruff lint, format check and mypy
scripts/preflight.sh --fix    # safe lint fixes/formatting, then full gate
bash scripts/build_native.sh # native interpreter library
```

No automated suite is maintained under the current owner policy. Use focused
one-off source/native/Qt checks when appropriate; a green static gate is not
vehicle acceptance. CI also runs `pip-audit` separately from preflight.

Project skills under [`.agents/`](.agents/README.md) are development utilities.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and `licenses/` for included
third-party notices. This is a personal-use project, not a validated public release.
