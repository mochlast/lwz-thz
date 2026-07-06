"""Climate entity for heating circuit 1.

Maps the pump's operating mode onto HVAC modes (a simplification — the full
mode set stays available on the operating-mode select):

- ``automatic``        -> AUTO
- ``day`` / ``manual`` -> HEAT
- everything else      -> OFF (standby, dhw, setback, emergency)

Target temperature reads/writes the day room setpoint (p01).
"""

from __future__ import annotations

from typing import Any, ClassVar

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ThzConfigEntry, ThzCoordinator
from .entity import ThzEntity
from .thzprotocol.writeparams import WRITE_PARAMS

PARALLEL_UPDATES = 1

_MODE_TO_HVAC = {
    "automatic": HVACMode.AUTO,
    "day": HVACMode.HEAT,
    "manual": HVACMode.HEAT,
}
_HVAC_TO_MODE = {
    HVACMode.AUTO: "automatic",
    HVACMode.HEAT: "day",
    HVACMode.OFF: "standby",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ThzClimate(entry.runtime_data)])


class ThzClimate(ThzEntity, ClimateEntity):
    """Heating circuit 1 as a thermostat."""

    _attr_name = None  # primary entity: carries the device name
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [
        HVACMode.AUTO,
        HVACMode.HEAT,
        HVACMode.OFF,
    ]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: ThzCoordinator) -> None:
        super().__init__(coordinator, unique_suffix="climate_hc1")
        param = WRITE_PARAMS["p01_room_temp_day"]
        self._attr_min_temp = param.min
        self._attr_max_temp = param.max
        self._attr_target_temperature_step = 0.5

    def _value(self, key: str) -> Any:
        return (self.coordinator.data or {}).get(key)

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = self._value("param.op_mode")
        if mode is None:
            return None
        return _MODE_TO_HVAC.get(mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction | None:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._value("sDisplay.heating_hc"):
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        return self._value("sHC1.inside_temp_rc")

    @property
    def target_temperature(self) -> float | None:
        return self._value("param.p01_room_temp_day")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.async_write_param(
            "p01_room_temp_day", float(temperature)
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.async_write_param("op_mode", _HVAC_TO_MODE[hvac_mode])
