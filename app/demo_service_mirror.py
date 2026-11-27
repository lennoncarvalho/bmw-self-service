"""ECU-timed electrochromic mirror behavior of the synthetic vehicle."""

import logging
import time

from app.service_mirror import mirror_profiles


class DemoMirror:
    """Keep the virtual ECU timer across stream disconnects."""

    def __init__(self) -> None:
        try:
            self._profiles = mirror_profiles()
        except (OSError, ValueError):
            logging.getLogger(__name__).warning(
                "Virtual mirror definitions unavailable", exc_info=True
            )
            self._profiles = {}
        self._until: dict[str, float] = {}

    def reply(self, *, variant: str, request: bytes, reads: dict[str, str]) -> bytes | None:
        """Serve the exact fitted mirror activation and effective dimming percentage."""
        profile = self._profiles.get(variant)
        if profile is None:
            return None
        start = profile["start"]
        state = bytes.fromhex(profile["state"]["request"])
        if request not in {state, bytes.fromhex(start["request"])}:
            return None
        raw = reads.get(state[1:].hex().upper(), "")
        present = profile["present"]["request"][2:].upper()
        active = self._until.get(variant, 0.0) > time.monotonic()
        if request == state:
            if active:
                return b"\x62" + state[1:] + bytes([100])
            return None  # Delegate ordinary and missing readings to the profile.
        if reads.get(present) != "01" or raw != "00" or active:
            return bytes((0x7F, request[0], 0x22))
        self._until[variant] = time.monotonic() + profile["seconds"]
        return bytes.fromhex(start["reply"])
