"""Button platform: set the device clock to Home Assistant's time."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ThzConfigEntry, ThzCoordinator
from .entity import ThzEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ThzClockSyncButton(entry.runtime_data)])


class ThzClockSyncButton(ThzEntity, ButtonEntity):
    """Sync the device clock; writes only the fields that are off (EEPROM)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "sync_clock"

    def __init__(self, coordinator: ThzCoordinator) -> None:
        super().__init__(coordinator, unique_suffix="sync_clock")

    async def async_press(self) -> None:
        await self.coordinator.async_sync_clock()
