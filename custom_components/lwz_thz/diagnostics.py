"""Diagnostics support (Settings → Devices → ⋯ → Download diagnostics)."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_HOST
from .coordinator import ThzConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ThzConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    now = time.monotonic()
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "firmware": coordinator.firmware,
        "connected": coordinator.client.is_connected,
        "last_update_success": coordinator.last_update_success,
        "poll_groups": [
            {
                "key": group.key,
                "interval": group.interval,
                "consecutive_errors": group.consecutive_errors,
                "due_in_seconds": round(max(0.0, group.next_due - now), 1),
            }
            for group in coordinator._groups
        ],
        "data": coordinator.data,
    }
