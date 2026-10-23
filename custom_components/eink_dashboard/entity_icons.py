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

"""Resolve Heading badge icons using Home Assistant's icon resources."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.icon import async_get_icons

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .const import Widget

_LOGGER = logging.getLogger(__name__)

# Match FALLBACK_DOMAIN_ICONS in HA frontend src/data/icons.ts. Domain
# definitions still come from the installed HA version's icons.json files;
# this table is only used when that domain has no icon definition.
_DOMAIN_FALLBACKS = {
    "ai_task": "star-four-points",
    "air_quality": "air-filter",
    "alert": "alert",
    "automation": "robot",
    "battery": "battery",
    "calendar": "calendar",
    "climate": "thermostat",
    "configurator": "cog",
    "conversation": "forum-outline",
    "counter": "counter",
    "date": "calendar",
    "datetime": "calendar-clock",
    "demo": "home-assistant",
    "device_tracker": "account",
    "door": "door-open",
    "garage_door": "garage-open",
    "gate": "gate",
    "google_assistant": "google-assistant",
    "group": "google-circles-communities",
    "homeassistant": "home-assistant",
    "homekit": "home-automation",
    "humidity": "water-percent",
    "illuminance": "brightness-6",
    "image_processing": "image-filter-frames",
    "image": "image",
    "infrared": "led-on",
    "input_boolean": "toggle-switch",
    "input_button": "button-pointer",
    "input_datetime": "calendar-clock",
    "input_number": "ray-vertex",
    "input_select": "format-list-bulleted",
    "input_text": "form-textbox",
    "lawn_mower": "robot-mower",
    "light": "lightbulb",
    "moisture": "water",
    "motion": "motion-sensor",
    "notify": "comment-alert",
    "number": "ray-vertex",
    "occupancy": "home-account",
    "persistent_notification": "bell",
    "person": "account",
    "plant": "flower",
    "power": "flash",
    "proximity": "apple-safari",
    "radio_frequency": "radio-tower",
    "remote": "remote",
    "scene": "palette",
    "schedule": "calendar-clock",
    "script": "script-text",
    "select": "format-list-bulleted",
    "sensor": "eye",
    "simple_alarm": "bell",
    "siren": "bullhorn",
    "stt": "microphone-message",
    "sun": "white-balance-sunny",
    "temperature": "thermometer",
    "text": "form-textbox",
    "time": "clock",
    "timer": "timer-outline",
    "template": "code-braces",
    "todo": "clipboard-list",
    "tts": "speaker-message",
    "vacuum": "robot-vacuum",
    "wake_word": "chat-sleep",
    "weather": "weather-partly-cloudy",
    "window": "window-closed",
    "zone": "map-marker-radius",
}


def _definition_icon(state: str, definition: dict[str, Any]) -> str | None:
    """Select an icon from HA's state, range, and default definitions.

    Uses the frontend's threshold rule: select the highest range key
    less than or equal to the numeric state. Definitions may be cached
    by HA, but the selection is evaluated for every state snapshot.

    Args:
        state: Raw entity state before locale formatting.
        definition: One icon resource from HA's icons.json data.

    Returns:
        The selected icon name, or None when no definition applies.
    """
    state_icons = definition.get("state", {})
    if icon := state_icons.get(state):
        return icon
    ranges = definition.get("range", {})
    try:
        value = float(state) if state.strip() else 0.0
    except ValueError:
        value = math.nan
    selected = -math.inf
    icon = None
    for threshold, candidate in ranges.items():
        try:
            number = float(threshold)
        except ValueError:
            continue
        if selected < number <= value:
            selected, icon = number, candidate
    return icon or definition.get("default")


def _state_icon(domain: str, state: str, attrs: dict[str, Any]) -> str | None:
    """Apply HA frontend's attribute-dependent state icon rules.

    Mirrors src/common/entity/state_icon.ts and its update and tracker
    helpers. Other domains are resolved from HA's icon resources.

    Args:
        domain: Entity domain, such as input_datetime or device_tracker.
        state: Current raw entity state.
        attrs: Attributes in the same state snapshot.

    Returns:
        The state icon, or None to continue resource resolution.
    """
    if domain == "update":
        if attrs.get("in_progress"):
            return "mdi:package-down"
        return "mdi:package-up" if state == "on" else "mdi:package"
    if domain == "device_tracker":
        source = attrs.get("source_type")
        if source == "router":
            return (
                "mdi:lan-connect" if state == "home" else "mdi:lan-disconnect"
            )
        if source in ("bluetooth", "bluetooth_le"):
            return (
                "mdi:bluetooth-connect" if state == "home" else "mdi:bluetooth"
            )
        return (
            "mdi:account-arrow-right" if state == "not_home" else "mdi:account"
        )
    if domain == "sun":
        return (
            "mdi:white-balance-sunny"
            if state == "above_horizon"
            else "mdi:weather-night"
        )
    if domain == "input_datetime":
        if not attrs.get("has_date"):
            return "mdi:clock"
        if not attrs.get("has_time"):
            return "mdi:calendar"
    return None


async def _load_resources(
    hass: HomeAssistant, category: str, integrations: set[str]
) -> dict[str, Any]:
    """Load icon definitions while isolating failed integrations.

    Args:
        hass: Running Home Assistant instance.
        category: HA icon resource category.
        integrations: Distinct domains or platforms needed by badges.

    Returns:
        Combined resources from integrations that loaded successfully.
    """
    resources: dict[str, Any] = {}
    for integration in integrations:
        try:
            resources.update(
                await async_get_icons(hass, category, {integration})
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Could not load %s icons for %s", category, integration
            )
    return resources


async def async_enrich_heading_icons(
    hass: HomeAssistant,
    widgets: list[Widget],
    states: dict[str, Any],
) -> None:
    """Resolve each Heading badge's current system icon into its snapshot.

    Follows ha-state-icon/entityIcon: registry override, state icon
    attribute, integration resource, attribute-dependent frontend rule,
    domain/device-class resource, then the frontend domain fallback.
    Only badge entities are resolved. Their ``entity_icon`` field is
    separate from attributes so other widgets retain their behaviour.

    Args:
        hass: Running Home Assistant instance.
        widgets: Widgets for this render, including unsaved preview edits.
        states: Mutable fresh state snapshots; resolved icons are added
            under ``entity_icon`` without mutating live HA states.
    """
    entity_ids = {
        badge if isinstance(badge, str) else badge.get("entity", "")
        for widget in widgets
        if widget.get("type") == "heading"
        for badge in widget.get("badges", [])
    }
    registry = er.async_get(hass)
    pending: dict[str, er.RegistryEntry | None] = {}
    for entity_id in entity_ids:
        if (data := states.get(entity_id)) is None:
            continue
        entry = registry.async_get(entity_id)
        icon = (entry.icon if entry else None) or data["attributes"].get(
            "icon"
        )
        if icon:
            data["entity_icon"] = icon
        else:
            pending[entity_id] = entry

    if not pending:
        return
    platforms = {
        entry.platform
        for entry in pending.values()
        if entry is not None and entry.translation_key
    }
    platform_icons = await _load_resources(hass, "entity", platforms)
    domains = {entity_id.split(".", 1)[0] for entity_id in pending}
    component_icons = await _load_resources(hass, "entity_component", domains)
    for entity_id, entry in pending.items():
        data = states[entity_id]
        attrs = data["attributes"]
        state = data["state"]
        domain = entity_id.split(".", 1)[0]
        icon = None
        if entry is not None and entry.translation_key:
            definition = (
                platform_icons.get(entry.platform, {})
                .get(domain, {})
                .get(entry.translation_key, {})
            )
            icon = _definition_icon(state, definition)
        if not icon:
            icon = _state_icon(domain, state, attrs)
        if not icon:
            definitions = component_icons.get(domain, {})
            definition = definitions.get(
                attrs.get("device_class")
            ) or definitions.get("_", {})
            icon = _definition_icon(state, definition)
        data["entity_icon"] = (
            icon or f"mdi:{_DOMAIN_FALLBACKS.get(domain, 'bookmark')}"
        )
