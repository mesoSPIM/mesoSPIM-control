"""Stable API for filter-wheel hardware plugins."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable


API_VERSION = "0.0.1"


@runtime_checkable
class FilterWheel(Protocol):
    """Runtime interface returned by a filter-wheel plugin factory."""

    def set_filter(self, filter_name: str, wait_until_done: bool = False) -> None:
        """Move to a configured filter position or raise on failure."""

    def close(self) -> None:
        """Release hardware resources. Implementations must be idempotent."""


@runtime_checkable
class FilterWheelPlugin(Protocol):
    """Factory interface implemented by filter-wheel plugin classes."""

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str: ...

    @classmethod
    def description(cls) -> str: ...

    @classmethod
    def required_parameters(cls) -> tuple[str, ...]:
        """Return operator-configurable keys required at initialization."""

    @classmethod
    def create(
        cls,
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> FilterWheel:
        """Validate configuration, connect to hardware, and return a driver."""
