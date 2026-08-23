"""Base entity for all LWZ/THZ entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MODEL, DOMAIN, OPT_MODEL, manufacturer_for
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
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        # The protocol has no model register, so the user names the unit in the
        # config flow; entries created before that option existed fall back.
        model = entry.options.get(OPT_MODEL, DEFAULT_MODEL)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=model,
            manufacturer=manufacturer_for(model),
            model=model,
            sw_version=coordinator.firmware,
        )

    @property
    def available(self) -> bool:
        description = getattr(self, "entity_description", None)
        value_key: str | None = getattr(description, "value_key", None)
        if value_key is None:
            return super().available
        return super().available and value_key in (self.coordinator.data or {})
