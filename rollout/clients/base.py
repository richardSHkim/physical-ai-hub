from __future__ import annotations

from typing import Any, Protocol


class PolicyClient(Protocol):
    @property
    def metadata(self) -> dict[str, Any]:
        """Server metadata advertised at connection time."""

    def infer(self, observation: dict[str, Any]) -> dict[str, Any]:
        """Run one inference request."""

    def reset(self) -> None:
        """Reset any client-side cached state."""

