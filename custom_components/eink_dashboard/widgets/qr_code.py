"""Build standard QR symbols with integer module geometry for e-ink."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import segno

from ._helpers import _color_context, _title_layout, _widget_dim

if TYPE_CHECKING:
    from ..const import DisplayConfig, Widget

# A standard QR requires four clear modules on every side.
_QUIET_ZONE = 4
# Smaller modules are too fragile for the intended e-ink displays.
_MIN_MODULE_PIXELS = 3
# Version 40-L holds at most 7,089 numeric characters. Reject larger
# inputs before running the encoder, including accidental large attributes.
_MAX_CONTENT_LENGTH = 7089


def _qr_content(widget: Widget, config: DisplayConfig) -> tuple[str, str]:
    """Resolve payload data without locale formatting or whitespace changes.

    Args:
        widget: Source selector, literal content, entity and optional
            attribute.
        config: Display configuration containing the entity state snapshot.

    Returns:
        Payload and an error message; the error is empty on success.
    """
    source = widget.get("source", "text")
    if source == "text":
        value = widget.get("content", "")
    elif source == "entity":
        state = config.get("states", {}).get(widget.get("entity", ""))
        if not state or state.get("state") in ("unknown", "unavailable", None):
            return "", "Entity unavailable"
        attribute = widget.get("attribute")
        if attribute:
            value = state.get("attributes", {}).get(attribute)
            if value is None:
                return "", "Attribute unavailable"
        else:
            value = state["state"]
    else:
        return "", "Invalid QR configuration"

    if value is None:
        return "", "No QR content"
    if not isinstance(value, (str, int, float, bool)):
        return "", "Invalid QR configuration"
    content = str(value)
    if not content.strip():
        return "", "No QR content"
    if len(content) > _MAX_CONTENT_LENGTH:
        return "", "QR content too long"
    return content, ""


def _build_qr_code_context(
    widget: Widget,
    config: DisplayConfig,
) -> dict[str, object]:
    """Build integer-aligned QR paths or a recoverable error placeholder.

    The quiet zone is included in the square fitted below the optional
    title. The module pitch is rounded down to whole pixels, and the
    resulting square is centered in the remaining viewport. Expected
    data errors stay local to this widget and never include the payload
    in logs or error messages.

    Args:
        widget: QR configuration with content or entity source, optional
            attribute and title, correction level L/M/Q/H (default M),
            and optional w/h dimensions (both default to 200 pixels).
        config: Display configuration containing entity states.

    Returns:
        Template variables for qr_code.svg.j2, including viewport,
        title, module paths and wrapped placeholder text.
    """
    # Import lazily because render.py also imports the widget registry.
    from ..render import DEFAULT_METRICS
    from ..svg_render import _fit_width_filter

    w = _widget_dim(widget, "w", 200)
    h = _widget_dim(widget, "h", 200)
    title = str(widget.get("title") or "")
    title_font, content_y, content_h = _title_layout(title, h)
    font = DEFAULT_METRICS.font_secondary
    content, error = _qr_content(widget, config)
    path = ""
    level = widget.get("error_correction", "M")
    if level not in ("L", "M", "Q", "H"):
        error = "Invalid QR configuration"
    if not error:
        try:
            # Explicit UTF-8 with ECI preserves non-ASCII payloads. Disable
            # error boosting so the selected correction level stays exact.
            code = segno.make_qr(
                content,
                error=level,
                encoding="utf-8",
                eci=True,
                boost_error=False,
            )
        except segno.DataOverflowError:
            error = "QR content too long"
        except ValueError:
            error = "Invalid QR configuration"
        else:
            modules = len(code.matrix) + 2 * _QUIET_ZONE
            pitch = min(w, content_h) // modules
            if pitch < _MIN_MODULE_PIXELS:
                error = "Enlarge widget or shorten content"
            else:
                # Include the quiet zone before computing the symbol's
                # origin; rounding the origin keeps every edge on pixels.
                x0 = (w - modules * pitch) // 2 + _QUIET_ZONE * pitch
                y0 = (
                    content_y
                    + (content_h - modules * pitch) // 2
                    + _QUIET_ZONE * pitch
                )
                segments = []
                for row_y, row in enumerate(code.matrix):
                    for col_x, dark in enumerate(row):
                        if dark:
                            x = x0 + col_x * pitch
                            y = y0 + row_y * pitch
                            segments.append(
                                f"M{x},{y}h{pitch}v{pitch}h{-pitch}z"
                            )
                path = "".join(segments)

    # Wrap placeholders to remain readable in the usual 200px viewport.
    # The desc element retains the full message for very small viewports.
    lines = textwrap.wrap(error, width=max(1, int(w / (font * 0.6))))
    line_h = round(font * 1.4)
    first_y = content_y + (content_h - len(lines) * line_h) // 2
    return {
        "w": w,
        "h": h,
        "title": _fit_width_filter(title, w, title_font) if title else "",
        "title_font": title_font,
        "error": error,
        "path": path,
        "text_x": w // 2,
        "font": font,
        "error_lines": [
            {"text": line, "y": first_y + i * line_h + line_h // 2}
            for i, line in enumerate(lines)
        ],
        **_color_context(),
    }
