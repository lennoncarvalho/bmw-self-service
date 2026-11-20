"""In-memory staging identities, separate from explicit project-file interchange."""

import json
import uuid
from typing import Any

from app.history_files import project_bytes


def new_record(origin: str = "draft") -> dict[str, Any]:
    """Create a stable local editor identity without trusted vehicle-outcome claims."""
    if origin not in ("draft", "imported"):
        raise ValueError("History editor records must be drafts or imports")
    return {"id": uuid.uuid4().hex, "origin": origin}


def new_workspace(project: dict[str, Any] | None = None, origin: str = "draft") -> dict[str, Any]:
    """Copy project data and create independent stable local identities for its entries."""
    if origin not in ("draft", "imported"):
        raise ValueError("History editor records must be drafts or imports")
    supplied = project if project is not None else {"schema_version": 1, "vin": None, "entries": []}
    # JSON round-trip detaches nested caller collections while retaining extension fields.
    copied = json.loads(project_bytes(supplied))
    return {
        "schema_version": 1,
        "kind": "history-workspace",
        "project": copied,
        "records": [new_record(origin) for _ in copied["entries"]],
    }
