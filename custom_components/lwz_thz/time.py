"""Time platform: start/end of the weekly program windows (Mo-So)."""

from __future__ import annotations

from datetime import datetime, time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ThzConfigEntry, ThzCoordinator
from .entity import ThzEntity
from .thzprotocol.programs import PROGRAM_SLOTS

PARALLEL_UPDATES = 1

# Fallback when one half is set while the slot was disabled.
DEFAULT_START = time(6, 0)
DEFAULT_END = time(22, 0)


def parse_program_time(value: str | None) -> time | None:
    if not value:
        return None
    return datetime.strptime(value, "%H:%M").time()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        ThzProgramTime(entry.runtime_data, slot_key, which)
        for slot_key in PROGRAM_SLOTS
        for which in ("start", "end")
    )


class ThzProgramTime(ThzEntity, TimeEntity):
    """One half (start or end) of a program window."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ThzCoordinator, slot_key: str, which: str) -> None:
        super().__init__(coordinator, unique_suffix=f"prog_{slot_key}_{which}")
        self._slot_key = slot_key
        self._which = which
        self._attr_translation_key = f"prog_{slot_key}_{which}"

    def _half(self, which: str) -> time | None:
        raw = (self.coordinator.data or {}).get(f"prog.{self._slot_key}.{which}")
        return parse_program_time(raw)

    @property
    def native_value(self) -> time | None:
        return self._half(self._which)

    async def async_set_value(self, value: time) -> None:
        start = self._half("start")
        end = self._half("end")
        remembered = self.coordinator.last_window(self._slot_key)
        if self._which == "start":
            start = value
            if end is None and remembered:
                end = parse_program_time(remembered[1])
            end = end or DEFAULT_END
        else:
            end = value
            if start is None and remembered:
                start = parse_program_time(remembered[0])
            start = start or DEFAULT_START
        self.coordinator.stage_program(self._slot_key, start, end)
