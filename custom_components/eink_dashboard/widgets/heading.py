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

"""Heading widget context builder."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    import markupsafe

from ..const import (
    COLOR_GRAY,
    DEFAULT_CARD_STYLE,
    DEFAULT_ROW_H,
    PADDING,
    DisplayConfig,
    Widget,
    color_to_hex,
)
from ._helpers import (
    _card_insets,
    _color_context,
    _fmt,
    _metrics_context,
    _resolve_icon_style,
    _resolve_icon_svg,
    _widget_dim,
)


class _HeadingBadgeDatum(NamedTuple):
    """Intermediate per-badge data used to compute final positions."""

    text: str
    text_w: int
    icon_w: int
    total_w: int
    show_icon: bool
    icon_svg: markupsafe.Markup | str


def _build_heading_context(
    widget: Widget,
    config: DisplayConfig,
) -> dict[str, object]:
    """Build Jinja2 template context for the heading widget.

    Renders an optional MDI icon and heading text on a single row,
    with optional entity badges flowing right-to-left from the right
    edge.  Mirrors HA's Heading card (``hui-heading-card.ts``).

    Heading style controls font size and fill:

    - ``"title"`` — Roboto Medium at ``font_primary``, black fill
      (default).
    - ``"subtitle"`` — Roboto Regular at ``font_secondary``, gray
      fill.

    Icon style controls circle rendering:

    - ``"none"`` — no circle; icon glyph sized to match the heading
      font (default).
    - ``"filled"`` — gray-filled circle at full ``icon_dia``.
    - ``"outlined"`` — white circle with black stroke at full
      ``icon_dia``.

    Badges are resolved right-to-left from the right edge; any badge
    that would overlap the heading text is silently omitted.
    Badge icons follow the current HA entity icon, shown by default.
    Legacy per-badge ``icon`` overrides are ignored; customise the
    entity in HA instead. Explicit ``show_icon: false`` still hides
    the icon, and ``show_state: false`` produces an icon-only badge.

    ``heading_align`` controls the heading text's horizontal anchor:

    - ``"left"`` — text starts at the icon-derived left edge
      (default).
    - ``"right"`` — text ends at the space left of any placed
      badges, or the right content edge when there are none.  The
      icon, if present, stays left-anchored.  If the text is too
      wide to fit in that space, its left edge is clamped to the
      icon-derived left edge instead of drawing over the icon.

    Args:
        widget: Widget config dict.  Recognised keys:
            ``heading`` (display text, default ``""``),
            ``heading_style`` (``"title"`` / ``"subtitle"``),
            ``heading_align`` (``"left"`` / ``"right"``),
            ``icon`` (MDI icon name, e.g. ``"mdi:home"``),
            ``icon_style`` (``"none"`` / ``"filled"`` /
            ``"outlined"``),
            ``badges`` (list of entity ID strings or badge config
            dicts),
            ``card_style``, ``x``, ``w``, ``h``.
        config: Display config with ``width``, ``states``, and
            ``display_levels``.

    Returns:
        Template context dict consumed by ``heading.svg.j2``.
        Returns ``{"w": …, "h": …, "has_content": False,
        **_color_context()}`` when there is nothing to render.
        Full context includes widget dimensions, card style,
        metrics, colors, icon geometry, heading text, and
        pre-positioned badge list.
    """
    from ..render import (
        _compute_metrics,
        _load_font,
    )
    from ..svg_render import _mdi_svg_filter

    x = widget.get("x", PADDING)
    svg_w = _widget_dim(widget, "w", config["width"] - x)
    svg_h = _widget_dim(widget, "h", DEFAULT_ROW_H)
    heading_text: str = widget.get("heading", "")
    heading_style: str = widget.get("heading_style", "title")
    heading_align: str = widget.get("heading_align", "left")
    icon_override = widget.get("icon")
    icon_style: str = widget.get("icon_style", "none")
    raw_badges = widget.get("badges", [])
    card_style = widget.get("card_style", DEFAULT_CARD_STYLE)
    states = config.get("states", {})
    display_levels = config.get("display_levels", 16)

    m = _compute_metrics(svg_h)
    x_off, r_inset, bar_width = _card_insets(m, card_style, display_levels)
    # Zero lpad/rpad when card_container already insets that side.
    lpad = m.padding if x_off == 0 else 0
    rpad = m.padding if r_inset == 0 else 0

    # Heading style: title (default) = large black;
    # subtitle = small gray.
    is_title = heading_style != "subtitle"
    font_sz = m.font_primary if is_title else m.font_secondary
    font_weight = "500" if is_title else "400"
    colors = _color_context()
    text_fill = colors["hex_black"] if is_title else colors["hex_gray"]

    # Icon resolution: glyph size depends on circle style.
    icon_outline, icon_no_circle = _resolve_icon_style(
        icon_style, display_levels=display_levels
    )
    # Widen the outline stroke on 2-level displays to avoid
    # dithering.
    icon_stroke_w = m.border * 3 if display_levels <= 2 else m.border
    glyph_sz = max(10, font_sz) if icon_no_circle else m.icon_inner
    icon_svg, _ = _resolve_icon_svg(
        icon_override,
        {},
        "",
        "",
        glyph_sz,
    )

    # Icon geometry: two modes depending on whether a circle
    # is drawn.
    icon_cx = icon_cy = icon_r = 0
    icon_fill = ""
    icon_glyph_x = icon_glyph_y = 0
    content_left = x_off + lpad
    if icon_svg:
        if icon_no_circle:
            # No circle: glyph sits flush at the content left
            # edge.
            icon_glyph_x = content_left
            icon_glyph_y = svg_h // 2 - glyph_sz // 2
            min_text_x = content_left + glyph_sz + m.inner_gap
        else:
            # Circle style: glyph is centred inside the circle.
            r = m.icon_dia // 2
            icon_cx = content_left + r
            icon_cy = svg_h // 2
            icon_r = r
            icon_fill = color_to_hex(COLOR_GRAY)
            icon_glyph_x = icon_cx - glyph_sz // 2
            icon_glyph_y = icon_cy - glyph_sz // 2
            min_text_x = content_left + m.icon_dia + m.inner_gap
    else:
        min_text_x = content_left

    text_y = svg_h // 2

    # Badge font and icon sizing.
    badge_font_sz = m.font_secondary
    badge_font = _load_font(badge_font_sz)
    badge_icon_sz = badge_font_sz
    # Keep each icon visually grouped with its value at every row size.
    badge_icon_gap = max(1, round(badge_font.getlength(" ")))

    # Resolve badge states and compute widths.
    badge_data: list[_HeadingBadgeDatum] = []
    for badge_cfg in raw_badges:
        if isinstance(badge_cfg, str):
            entity_id: str = badge_cfg
            show_icon = True
            show_state = True
        else:
            entity_id = badge_cfg.get("entity", "")
            show_icon = badge_cfg.get("show_icon", True)
            show_state = badge_cfg.get("show_state", True)
        state = states.get(entity_id)
        if state is None:
            continue
        attrs = state.get("attributes", {})
        state_val = state.get("state", "")
        unit = attrs.get("unit_of_measurement", "")
        fmtd = _fmt(state_val, config) if show_state else ""
        badge_text = f"{fmtd}{unit}" if show_state else ""

        badge_icon_svg: markupsafe.Markup | str = ""
        if show_icon:
            # The async pipeline resolves HA's current icon. Never let
            # widget overrides or local class maps replace that choice.
            badge_icon = state.get("entity_icon", attrs.get("icon", ""))
            if isinstance(badge_icon, str) and badge_icon.startswith("mdi:"):
                with contextlib.suppress(FileNotFoundError, ValueError):
                    badge_icon_svg = _mdi_svg_filter(
                        badge_icon[4:], badge_icon_sz
                    )

        if not badge_icon_svg and not badge_text:
            continue
        icon_w = (
            badge_icon_sz + (badge_icon_gap if badge_text else 0)
            if badge_icon_svg
            else 0
        )
        text_w = round(badge_font.getlength(badge_text))
        badge_data.append(
            _HeadingBadgeDatum(
                text=badge_text,
                text_w=text_w,
                icon_w=icon_w,
                total_w=icon_w + text_w,
                show_icon=show_icon,
                icon_svg=badge_icon_svg,
            )
        )

    # Reserve the heading's measured width for either alignment before
    # placing badges. Otherwise adding an icon can push a badge onto
    # the text even though it still clears the heading's left edge.
    heading_w = 0
    if heading_text:
        heading_font = _load_font(font_sz, medium=is_title)
        heading_w = round(heading_font.getlength(heading_text))
    badge_min_left = min_text_x + heading_w + m.inner_gap

    # Pack from the right, dropping a badge and the remaining badges to
    # its left in config order when it would overlap the heading.
    badge_right = svg_w - r_inset - rpad
    rendered_badges: list[dict[str, object]] = []
    for bd in reversed(badge_data):
        new_right = badge_right - bd.total_w
        if new_right < badge_min_left:
            break
        badge_cy = svg_h // 2
        rendered_badges.insert(
            0,
            {
                "text": bd.text,
                "text_x": badge_right - bd.text_w,
                "text_y": badge_cy,
                "show_icon": bd.show_icon,
                "icon_svg": bd.icon_svg,
                "icon_x": new_right,
                "icon_y": badge_cy - badge_icon_sz // 2,
            },
        )
        badge_right = new_right - m.inner_gap

    # Right alignment anchors the text to the space left of any
    # placed badges (or the right content edge when there are none),
    # rather than the icon-derived left edge.  If the heading text is
    # wide enough that anchoring it there would push its left edge
    # past ``min_text_x``, clamp the anchor so the text never draws
    # over the icon — matching the left-aligned case, where text
    # simply grows rightward from ``min_text_x`` instead.
    text_x = min_text_x
    text_anchor = "start"
    if heading_align == "right":
        text_anchor = "end"
        text_x = badge_right
        if heading_text:
            text_x = max(text_x - heading_w, min_text_x) + heading_w

    has_content = bool(heading_text) or bool(icon_svg) or bool(rendered_badges)

    if not has_content:
        return {
            "w": svg_w,
            "h": svg_h,
            "has_content": False,
            **colors,
        }

    return {
        "w": svg_w,
        "h": svg_h,
        "has_content": True,
        "card_style": card_style,
        "bar_width": bar_width,
        **_metrics_context(m),
        **colors,
        # Icon geometry (only used when icon_svg is truthy).
        "icon_svg": icon_svg,
        "icon_cx": icon_cx,
        "icon_cy": icon_cy,
        "icon_r": icon_r,
        "icon_stroke_w": icon_stroke_w,
        "icon_fill": icon_fill,
        "icon_color": colors["hex_black"],
        "icon_outline": icon_outline,
        "icon_no_circle": icon_no_circle,
        "icon_glyph_x": icon_glyph_x,
        "icon_glyph_y": icon_glyph_y,
        # Heading text.
        "heading": heading_text,
        "font_sz": font_sz,
        "font_weight": font_weight,
        "text_fill": text_fill,
        "text_x": text_x,
        "text_y": text_y,
        "text_anchor": text_anchor,
        # Badges (pre-positioned, empty list when none fit).
        "badges": rendered_badges,
        "badge_font_sz": badge_font_sz,
    }
