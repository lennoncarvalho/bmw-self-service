#!/usr/bin/env bash
#
# Preflight quality gate — mirrors .github/workflows/python-ci.yml.
#
# EVERY push must pass all three gates over the FULL app code
# (app/, ui/, main.py):
#
#   1. ruff check              lint (pycodestyle, pyflakes, isort, bugbear,
#                              comprehensions, pyupgrade, simplify)
#   2. ruff format --check     formatting (a different command from lint —
#                              running only `ruff check` is NOT enough)
#   3. mypy app/ ui/           static type checking
#
# Usage:
#   scripts/preflight.sh          # run all gates
#   scripts/preflight.sh --fix    # apply ruff fixes/formatting first
#
# Exit code: 0 = all gates pass, 1 = at least one gate failed.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

TARGETS=(app/ ui/ main.py)
FAILED=()

# ── tool resolution ─────────────────────────────────────────────────────────
# Prefer the project virtualenv so local runs match CI exactly.

if [ -x .venv/bin/python3 ]; then
    PYTHON=.venv/bin/python3
else
    PYTHON=python3
fi

if [ -x .venv/bin/ruff ]; then
    ruff() { .venv/bin/ruff "$@"; }
elif command -v ruff >/dev/null 2>&1; then
    ruff() { command ruff "$@"; }
elif command -v pipx >/dev/null 2>&1; then
    ruff() { pipx run ruff "$@"; }
else
    echo "preflight: ruff not found — run '.venv/bin/pip install ruff' or install pipx" >&2
    exit 1
fi

mypy_run() {
    if "$PYTHON" -m mypy --version >/dev/null 2>&1; then
        "$PYTHON" -m mypy "$@"
    elif command -v mypy >/dev/null 2>&1; then
        command mypy "$@"
    elif command -v pipx >/dev/null 2>&1; then
        pipx run mypy "$@"
    else
        echo "preflight: mypy not found — run '$PYTHON -m pip install mypy'" >&2
        return 1
    fi
}

# ── optional autofix ────────────────────────────────────────────────────────

if [ "${1:-}" = "--fix" ]; then
    echo "── applying ruff fixes"
    ruff check --fix "${TARGETS[@]}" || true
    ruff format "${TARGETS[@]}" || true
    echo
fi

# ── gates ───────────────────────────────────────────────────────────────────

gate() {
    local label="$1"
    shift
    echo "── $label"
    if "$@"; then
        echo "   ✓ $label"
    else
        echo "   ✗ $label FAILED"
        FAILED+=("$label")
    fi
    echo
}

gate "ruff check" ruff check "${TARGETS[@]}"
gate "ruff format --check" ruff format --check "${TARGETS[@]}"
gate "mypy" mypy_run app/ ui/ main.py --ignore-missing-imports

# ── result ──────────────────────────────────────────────────────────────────

if [ ${#FAILED[@]} -eq 0 ]; then
    echo "✓ preflight passed — safe to push."
    exit 0
fi

echo "✗ preflight failed: ${FAILED[*]}"
echo "  Fix the errors above, then re-run scripts/preflight.sh."
echo "  Never push with a failing gate — CI runs the same three checks."
exit 1
