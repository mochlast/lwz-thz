"""Sensor platform."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OPT_ENABLE_HC2, OPT_ENABLE_SOLAR
from .coordinator import ThzConfigEntry
from .descriptions import SENSORS, ThzSensorDescription
from .entity import ThzEntity

PARALLEL_UPDATES = 0


def _enabled_features(entry: ThzConfigEntry) -> set[str]:
    features: set[str] = set()
    if entry.options.get(OPT_ENABLE_HC2, False):
        features.add("hc2")
    if entry.options.get(OPT_ENABLE_SOLAR, False):
        features.add("solar")
    return features


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    features = _enabled_features(entry)
    async_add_entities(
        ThzSensor(entry.runtime_data, description)
        for description in SENSORS
        if description.feature is None or description.feature in features
    )


class ThzSensor(ThzEntity, SensorEntity):
    """Sensor mapping one coordinator data key."""

    entity_description: ThzSensorDescription

    @property
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.value_key)
