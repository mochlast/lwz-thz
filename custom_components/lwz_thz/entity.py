"""Base entity for all LWZ/THZ entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThzCoordinator


class ThzEntity(CoordinatorEntity[ThzCoordinator]):
    """Coordinator entity, optionally bound to one coordinator data key."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThzCoordinator,
        description: EntityDescription | None = None,
        *,
        unique_suffix: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        if description is not None:
            self.entity_description = description
        suffix = unique_suffix or (description.key if description else None)
        if suffix is None:
            raise ValueError("either description or unique_suffix is required")
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="LWZ 304 Trend",
            manufacturer="Stiebel Eltron / Tecalor",
            model="LWZ/THZ integral heat pump",
            sw_version=coordinator.firmware,
        )

    @property
    def available(self) -> bool:
        description = getattr(self, "entity_description", None)
        value_key: str | None = getattr(description, "value_key", None)
        if value_key is None:
            return super().available
        return super().available and value_key in (self.coordinator.data or {})
