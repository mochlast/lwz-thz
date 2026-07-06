"""Binary sensor platform."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ThzConfigEntry
from .descriptions import BINARY_SENSORS, ThzBinarySensorDescription
from .entity import ThzEntity
from .sensor import _enabled_features

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    features = _enabled_features(entry)
    async_add_entities(
        ThzBinarySensor(entry.runtime_data, description)
        for description in BINARY_SENSORS
        if description.feature is None or description.feature in features
    )


class ThzBinarySensor(ThzEntity, BinarySensorEntity):
    """Binary sensor mapping one coordinator data key."""

    entity_description: ThzBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get(self.entity_description.value_key)
        return None if value is None else bool(value)
