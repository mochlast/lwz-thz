"""Select platform (operating mode, fan stages)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ThzConfigEntry
from .descriptions import SELECTS, ThzSelectDescription
from .entity import ThzEntity
from .sensor import _enabled_features

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    features = _enabled_features(entry)
    async_add_entities(
        ThzSelect(entry.runtime_data, description)
        for description in SELECTS
        if description.feature is None or description.feature in features
    )


class ThzSelect(ThzEntity, SelectEntity):
    """Writable parameter exposed as a select."""

    entity_description: ThzSelectDescription

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.data.get(self.entity_description.value_key)
        for option, value in self.entity_description.option_to_value.items():
            if value == raw:
                return option
        return None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write_param(
            self.entity_description.param_key,
            self.entity_description.option_to_value[option],
        )
