"""Switch platform: weekly program windows and on/off parameters."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ThzConfigEntry, ThzCoordinator
from .descriptions import SWITCHES, ThzSwitchDescription
from .entity import ThzEntity
from .sensor import _enabled_features
from .thzprotocol.programs import PROGRAM_SLOTS
from .time import DEFAULT_END, DEFAULT_START, parse_program_time

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        ThzProgramSwitch(entry.runtime_data, slot_key) for slot_key in PROGRAM_SLOTS
    )
    features = _enabled_features(entry)
    async_add_entities(
        ThzParamSwitch(entry.runtime_data, description)
        for description in SWITCHES
        if description.feature is None or description.feature in features
    )


class ThzParamSwitch(ThzEntity, SwitchEntity):
    """Writable 0/1 parameter exposed as a switch."""

    entity_description: ThzSwitchDescription

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get(self.entity_description.value_key)
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_param(self.entity_description.param_key, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_param(self.entity_description.param_key, 0)


class ThzProgramSwitch(ThzEntity, SwitchEntity):
    """Active state of a program window (off = n.a. in the device)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ThzCoordinator, slot_key: str) -> None:
        super().__init__(coordinator, unique_suffix=f"prog_{slot_key}_active")
        self._slot_key = slot_key
        self._attr_translation_key = f"prog_{slot_key}_active"

    def _half(self, which: str):
        raw = (self.coordinator.data or {}).get(f"prog.{self._slot_key}.{which}")
        return parse_program_time(raw)

    @property
    def is_on(self) -> bool | None:
        key = f"prog.{self._slot_key}.start"
        if key not in (self.coordinator.data or {}):
            return None
        return self._half("start") is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        start = self._half("start")
        end = self._half("end")
        # Re-enabling restores the last known window, not the defaults.
        if (
            start is None
            and end is None
            and (remembered := self.coordinator.last_window(self._slot_key))
        ):
            start = parse_program_time(remembered[0])
            end = parse_program_time(remembered[1])
        self.coordinator.stage_program(
            self._slot_key, start or DEFAULT_START, end or DEFAULT_END
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.stage_program(self._slot_key, None, None)
