"""Number platform (writable setpoints and durations).

Writes are debounced: rapid up/down clicks update the displayed value
optimistically and only the final value is written to the pump (one serial
write cycle instead of one per click). On write failure the entity reverts
to the last verified value and a warning is logged.
"""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .coordinator import ThzConfigEntry, ThzCoordinator
from .descriptions import NUMBERS, ThzNumberDescription
from .entity import ThzEntity
from .sensor import _enabled_features

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

WRITE_DEBOUNCE = 1.0  # seconds of click silence before the value is written


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    features = _enabled_features(entry)
    async_add_entities(
        ThzNumber(entry.runtime_data, description)
        for description in NUMBERS
        if description.feature is None or description.feature in features
    )


class ThzNumber(ThzEntity, NumberEntity):
    """Writable parameter exposed as a number, with debounced writes."""

    entity_description: ThzNumberDescription

    def __init__(
        self, coordinator: ThzCoordinator, description: ThzNumberDescription
    ) -> None:
        super().__init__(coordinator, description)
        self._pending_value: float | None = None
        self._cancel_debounce: CALLBACK_TYPE | None = None

    @property
    def native_value(self) -> float | None:
        if self._pending_value is not None:
            return self._pending_value
        value = self.coordinator.data.get(self.entity_description.value_key)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        self._pending_value = value
        self.async_write_ha_state()  # show the click immediately
        if self._cancel_debounce is not None:
            self._cancel_debounce()
        self._cancel_debounce = async_call_later(
            self.hass, WRITE_DEBOUNCE, self._async_flush
        )

    async def _async_flush(self, _now) -> None:
        self._cancel_debounce = None
        value = self._pending_value
        if value is None:
            return
        try:
            await self.coordinator.async_write_param(
                self.entity_description.param_key, value
            )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Writing %s = %s failed, reverting to device value: %s",
                self.entity_description.param_key,
                value,
                err,
            )
        finally:
            # Only clear if no newer click arrived while we were writing.
            if self._pending_value == value:
                self._pending_value = None
                self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_debounce is not None:
            self._cancel_debounce()
            self._cancel_debounce = None
        await super().async_will_remove_from_hass()
