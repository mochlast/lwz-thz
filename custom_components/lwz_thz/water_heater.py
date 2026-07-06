"""Water heater entity (DHW storage).

Current temperature comes from the storage sensor, the target writes the
day DHW setpoint (p04). Night/standby setpoints stay on their numbers.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ThzConfigEntry, ThzCoordinator
from .entity import ThzEntity
from .thzprotocol.writeparams import WRITE_PARAMS

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ThzWaterHeater(entry.runtime_data)])


class ThzWaterHeater(ThzEntity, WaterHeaterEntity):
    """DHW storage as a water heater."""

    _attr_translation_key = "dhw"
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: ThzCoordinator) -> None:
        super().__init__(coordinator, unique_suffix="water_heater_dhw")
        param = WRITE_PARAMS["p04_dhw_temp_day"]
        self._attr_min_temp = param.min
        self._attr_max_temp = param.max

    def _value(self, key: str) -> Any:
        return (self.coordinator.data or {}).get(key)

    @property
    def current_temperature(self) -> float | None:
        return self._value("sGlobal.dhw_temp")

    @property
    def target_temperature(self) -> float | None:
        return self._value("param.p04_dhw_temp_day")

    @property
    def current_operation(self) -> str | None:
        mode = self._value("sDHW.dhw_op_mode")
        return None if mode is None else str(mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.async_write_param("p04_dhw_temp_day", float(temperature))
