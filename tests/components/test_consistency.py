"""Every entity description must reference an existing register key."""

from custom_components.lwz_thz.descriptions import (
    BINARY_SENSORS,
    NUMBERS,
    SELECTS,
    SENSORS,
)
from custom_components.lwz_thz.thzprotocol.mappings import OP_MODE_REVERSE
from custom_components.lwz_thz.thzprotocol.registers import BLOCKS, ENERGY
from custom_components.lwz_thz.thzprotocol.writeparams import WRITE_PARAMS


def _registry_keys() -> set[str]:
    keys = {
        f"{block.key}.{field.key}"
        for block in BLOCKS.values()
        for field in block.fields
    }
    keys.update(f"energy.{meter}" for meter in ENERGY)
    return keys


def test_sensor_value_keys_exist() -> None:
    valid = _registry_keys()
    missing = [d.key for d in SENSORS if d.value_key not in valid]
    assert not missing, f"sensor descriptions with unknown value_key: {missing}"


def test_binary_sensor_value_keys_exist() -> None:
    valid = _registry_keys()
    missing = [d.key for d in BINARY_SENSORS if d.value_key not in valid]
    assert not missing, f"binary sensor descriptions with unknown value_key: {missing}"


def test_description_keys_unique() -> None:
    keys = [d.key for d in SENSORS] + [d.key for d in BINARY_SENSORS]
    keys += [d.key for d in NUMBERS] + [d.key for d in SELECTS]
    duplicates = {key for key in keys if keys.count(key) > 1}
    assert not duplicates, f"duplicate description keys: {duplicates}"


def test_number_select_param_keys_exist() -> None:
    missing = [d.key for d in NUMBERS if d.param_key not in WRITE_PARAMS]
    missing += [d.key for d in SELECTS if d.param_key not in WRITE_PARAMS]
    assert not missing, f"descriptions with unknown param_key: {missing}"


def test_every_write_param_has_exactly_one_entity() -> None:
    used = [d.param_key for d in NUMBERS] + [d.param_key for d in SELECTS]
    assert sorted(used) == sorted(WRITE_PARAMS)


def test_select_options_match_mapping() -> None:
    for description in SELECTS:
        assert set(description.options) == set(description.option_to_value)
        if description.key == "op_mode":
            unknown = set(description.option_to_value.values()) - set(OP_MODE_REVERSE)
            assert not unknown, f"op_mode options without protocol code: {unknown}"


def test_translations_cover_all_entities() -> None:
    import json
    from pathlib import Path

    translations_dir = (
        Path(__file__).resolve().parents[2]
        / "custom_components"
        / "lwz_thz"
        / "translations"
    )
    for language_file in ("en.json", "de.json"):
        translations = json.loads((translations_dir / language_file).read_text())
        entity_names = translations["entity"]
        missing = [d.key for d in SENSORS if d.key not in entity_names["sensor"]]
        missing += [
            d.key for d in BINARY_SENSORS if d.key not in entity_names["binary_sensor"]
        ]
        missing += [d.key for d in NUMBERS if d.key not in entity_names["number"]]
        missing += [d.key for d in SELECTS if d.key not in entity_names["select"]]
        assert not missing, f"{language_file} missing entity names: {missing}"

        for description in SELECTS:
            states = entity_names["select"][description.key].get("state", {})
            missing_states = [o for o in description.options if o not in states]
            assert not missing_states, (
                f"{language_file} select {description.key} missing states: "
                f"{missing_states}"
            )
