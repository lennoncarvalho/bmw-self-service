# BMW Self Service overlay

This overlay precedes the vendored upstream advice. Keep the existing Qt Widgets,
QScrollArea/QVBoxLayout, QSS and CarWorker(QThread) architecture. QML, model/view
and asyncio examples are background reference, not migration instructions.
Use Python 3.13 target, 100-column lines, existing dependencies and no test suite.

For implementation as well as review, trace object/thread ownership and actual
signal delivery. QThread objects live in their creator thread; normal method
calls do not move work to `run()`. A QTimer slot that calls sockets still blocks
the GUI. Keep network work and lock waits off the GUI, including heartbeats.
Do not assume a Python lambda establishes the desired QObject receiver context.
Use appropriate QObject slots and queued delivery for UI updates.

Keep thread references alive until actual completion. Separate result delivery
from QThread's lifecycle `finished()`; flag shadowed built-in signals. Cooperative
cancellation must interrupt/settle socket operations safely. `quit()` does not
stop a blocking `run()` and a queued cancel slot cannot execute while its thread
is blocked in work. Avoid GUI-thread waits and forced termination.

Parentless QObjects can be valid when ownership is deliberate; absence of a
parent alone is not proof of a leak. Review real lifetimes, pending signals and
shutdown ordering. Ignore stale results after disconnect/reconnect using explicit
session identity. Do not reuse mutable payloads across queued callbacks.

Bound/lazily populate widget lists; clipping painting does not avoid construction,
layout and memory costs. Keep styling centralized as the current convention.
Use visual checks for empty/loading/partial/error states, keyboard navigation,
focus, disabled actions and write/readback outcomes. A warning dialog does not
repair an unsafe operation.

`review.py` and generic examples are optional references, not required commands;
do not execute repository-wide mutation or tests from skill snippets. Report
concrete triggers and consequences with source lines before recommending changes.
