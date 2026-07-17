"""Backwards-compatible shim. Prefer importing from :mod:`euroclaw.settings`."""

from euroclaw.settings import (
    Settings,
    get_settings,
    validate_settings,
    current_settings,
)

__all__ = ["Settings", "get_settings", "validate_settings", "current_settings"]
