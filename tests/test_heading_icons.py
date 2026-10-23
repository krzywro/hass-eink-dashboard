# Copyright 2026 Andreas Schneider
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Heading badges use Home Assistant's current icon definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eink_dashboard import _build_display_config
from custom_components.eink_dashboard.const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _config(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    """Build the preview config for a heading containing one badge.

    Args:
        hass: Home Assistant test instance containing the entity state.
        entity_id: Entity to include in the heading's badge list.

    Returns:
        Production display config with enriched state snapshots.
    """
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "entry": entry,
        "widgets": [{"type": "heading", "badges": [entity_id]}],
    }
    return await _build_display_config(hass, entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "state", "attributes", "expected"),
    [
        ("sensor.example", "42", {}, "mdi:eye"),
        ("sensor.example", "42", {"device_class": "voltage"}, "mdi:sine-wave"),
        (
            "sensor.example",
            "57",
            {"device_class": "battery"},
            "mdi:battery-50",
        ),
        (
            "sensor.example",
            "unknown",
            {"device_class": "battery"},
            "mdi:battery-unknown",
        ),
        (
            "sensor.example",
            "68",
            {"device_class": "wind_direction"},
            "mdi:arrow-left",
        ),
        (
            "binary_sensor.example",
            "on",
            {"device_class": "door"},
            "mdi:door-open",
        ),
        ("switch.example", "off", {}, "mdi:toggle-switch-variant-off"),
        ("time.example", "12:30:00", {}, "mdi:clock"),
        (
            "input_datetime.example",
            "12:30:00",
            {"has_date": False, "has_time": True},
            "mdi:clock",
        ),
        (
            "device_tracker.example",
            "home",
            {"source_type": "router"},
            "mdi:lan-connect",
        ),
        ("update.example", "off", {"in_progress": True}, "mdi:package-down"),
        ("sun.example", "below_horizon", {}, "mdi:weather-night"),
        ("custom_domain.example", "on", {}, "mdi:bookmark"),
    ],
)
async def test_uses_ha_component_and_state_icons(
    hass: HomeAssistant,
    entity_id: str,
    state: str,
    attributes: dict[str, Any],
    expected: str,
) -> None:
    # Real HA definitions supply defaults, states, ranges and fallbacks.
    """Resolve general entities without dashboard-specific class maps."""
    hass.states.async_set(entity_id, state, attributes)
    config = await _config(hass, entity_id)
    assert config["states"][entity_id].get("entity_icon") == expected


async def test_registry_override_has_highest_priority(
    hass: HomeAssistant,
) -> None:
    # Registry customisation wins even if the state has another icon.
    """Respect the icon selected in HA entity settings."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "sensor",
        "moon",
        "custom",
        suggested_object_id="example",
        translation_key="phase",
    )
    registry.async_update_entity(entry.entity_id, icon="mdi:home")
    hass.states.async_set(
        entry.entity_id,
        "full_moon",
        {
            "device_class": "temperature",
            "icon": "mdi:thermometer",
        },
    )
    config = await _config(hass, entry.entity_id)
    assert config["states"][entry.entity_id].get("entity_icon") == "mdi:home"


async def test_state_attribute_icon_has_priority(
    hass: HomeAssistant,
) -> None:
    # An integration-supplied icon is not replaced by its device class.
    """Preserve explicit state icons including non-MDI icon names."""
    hass.states.async_set(
        "sensor.example",
        "42",
        {
            "device_class": "temperature",
            "icon": "custom:example",
        },
    )
    config = await _config(hass, "sensor.example")
    assert config["states"]["sensor.example"].get("entity_icon") == (
        "custom:example"
    )


async def test_platform_icon_tracks_current_state(
    hass: HomeAssistant,
) -> None:
    # Definitions may be cached, but the selected icon must stay current.
    """Re-evaluate integration icons for each fresh snapshot."""
    entry = er.async_get(hass).async_get_or_create(
        "sensor",
        "moon",
        "dynamic",
        suggested_object_id="example",
        translation_key="phase",
    )
    for state, expected in [
        ("full_moon", "mdi:moon-full"),
        ("new_moon", "mdi:moon-new"),
    ]:
        hass.states.async_set(
            entry.entity_id,
            state,
            {
                "device_class": "temperature",
            },
        )
        config = await _config(hass, entry.entity_id)
        assert config["states"][entry.entity_id].get("entity_icon") == expected
    assert "icon" not in hass.states.get(entry.entity_id).attributes


async def test_range_icon_tracks_current_numeric_state(
    hass: HomeAssistant,
) -> None:
    # A cached HA definition must not cache the icon for a previous value.
    """Select the current icon from HA's numeric thresholds."""
    for value, expected in [
        ("57", "mdi:battery-50"),
        ("83", "mdi:battery-80"),
        ("-1", "mdi:battery-unknown"),
    ]:
        hass.states.async_set(
            "sensor.example",
            value,
            {
                "device_class": "battery",
            },
        )
        config = await _config(hass, "sensor.example")
        assert config["states"]["sensor.example"]["entity_icon"] == expected


async def test_failed_integration_uses_system_domain_definition(
    hass: HomeAssistant,
) -> None:
    # One broken platform must not block component definitions or rendering.
    """Keep resolving a badge if integration resources cannot load."""
    entry = er.async_get(hass).async_get_or_create(
        "sensor",
        "missing_platform",
        "example",
        suggested_object_id="example",
        translation_key="value",
    )
    hass.states.async_set(
        entry.entity_id,
        "42",
        {
            "device_class": "temperature",
        },
    )
    resources = [
        RuntimeError("broken integration"),
        {
            "sensor": {"temperature": {"default": "mdi:thermometer"}},
        },
    ]
    with patch(
        "custom_components.eink_dashboard.entity_icons.async_get_icons",
        AsyncMock(side_effect=resources),
    ):
        config = await _config(hass, entry.entity_id)
    assert (
        config["states"][entry.entity_id]["entity_icon"] == "mdi:thermometer"
    )


async def test_unrelated_entities_are_not_enriched(
    hass: HomeAssistant,
) -> None:
    # Resolving Heading icons must not change icon behaviour in other widgets.
    """Only attach resolved icons to the requested badge entities."""
    hass.states.async_set("sensor.example", "42", {"icon": "mdi:home"})
    hass.states.async_set("sensor.other", "57", {"device_class": "battery"})
    config = await _config(hass, "sensor.example")
    assert "entity_icon" not in config["states"]["sensor.other"]
