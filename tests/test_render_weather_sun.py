"""Verify the weather widget's optional sunrise/sunset column."""

from __future__ import annotations

from math import ceil
from typing import ClassVar
from xml.etree import ElementTree as ET

import pytest

from custom_components.eink_dashboard.render import render_dashboard
from custom_components.eink_dashboard.svg_render import render_widget_svg
from tests.helpers import (
    assert_all_white,
    assert_has_dark_pixels,
    assert_scales_proportionally,
    assert_vertically_centered,
    content_bbox,
    make_config,
    render_to_image,
)
from tests.test_render_weather import MOCK_WEATHER_STATE

MOCK_SUN_STATE = {
    "state": "above_horizon",
    "attributes": {
        "next_rising": "2026-10-23T04:42:00+00:00",
        "next_setting": "2026-10-23T15:28:00+00:00",
    },
}


class TestWeatherSunTimes:
    """Check column selection, local times, and visible geometry."""

    _WIDGET: ClassVar[dict[str, object]] = {
        "type": "weather",
        "entity": "weather.home",
        "x": 0,
        "y": 0,
        "w": 460,
        "mode": "current",
        "show_sun_times": True,
    }
    _DEFAULTS: ClassVar[dict[str, object]] = {
        "width": 1000,
        "height": 500,
        "time_zone": "Europe/Warsaw",
        "time_format": "24",
        "language": "pl",
        "states": {**MOCK_WEATHER_STATE, "sun.sun": MOCK_SUN_STATE},
    }

    def _config(self, **overrides: object) -> dict[str, object]:
        """Build a display configuration with optional overrides.

        Args:
            **overrides: Display configuration values to replace.

        Returns:
            A fresh display configuration for this test.
        """
        return make_config(self._DEFAULTS, **overrides)

    def test_disabled_matches_existing_default(self) -> None:
        # Existing dashboards keep exactly the same output by default.
        widget = dict(self._WIDGET)
        del widget["show_sun_times"]
        assert render_dashboard([widget], self._config()) == render_dashboard(
            [{**widget, "show_sun_times": False}], self._config()
        )

    @pytest.mark.parametrize("show_sun_times", [False, True])
    @pytest.mark.parametrize("width", [460, 620])
    @pytest.mark.parametrize("temperature", [7, 11.7])
    def test_temperature_is_horizontally_centered(
        self, show_sun_times: bool, width: int, temperature: float
    ) -> None:
        # Short and long temperatures stay on the widget's center axis.
        config = self._config(
            states={
                **self._DEFAULTS["states"],
                "weather.home": {
                    **MOCK_WEATHER_STATE["weather.home"],
                    "attributes": {
                        **MOCK_WEATHER_STATE["weather.home"]["attributes"],
                        "temperature": temperature,
                    },
                },
            }
        )
        widget = {
            **self._WIDGET,
            "w": width,
            "show_sun_times": show_sun_times,
        }
        img = render_to_image([widget], config)
        bbox = content_bbox(img, 100, 10, width - 120, 90)
        assert bbox is not None
        assert abs((bbox[0] + bbox[2]) / 2 - width / 2) <= 3

    def test_replaces_only_the_top_right_column(self) -> None:
        # Sun times replace hi/lo/precip while the bar and details stay put.
        sun = render_to_image([self._WIDGET], self._config())
        forecast = render_to_image(
            [{**self._WIDGET, "show_sun_times": False}], self._config()
        )
        assert (
            sun.crop((320, 10, 450, 90)).tobytes()
            != forecast.crop((320, 10, 450, 90)).tobytes()
        )
        assert (
            sun.crop((0, 92, 460, 250)).tobytes()
            == forecast.crop((0, 92, 460, 250)).tobytes()
        )

    @pytest.mark.parametrize("mode", ["full", "current", "forecast"])
    def test_sun_times_without_forecast(self, mode: str) -> None:
        # Sun times work without forecast data, including forecast fallback.
        config = self._config(
            states={
                "weather.home": {
                    "state": "sunny",
                    "attributes": {"temperature": 22},
                },
                "sun.sun": MOCK_SUN_STATE,
            }
        )
        img = render_to_image([{**self._WIDGET, "mode": mode}], config)
        assert_has_dark_pixels(img, 350, 10, 450, 50)
        assert_has_dark_pixels(img, 350, 50, 450, 90)

    def test_forecast_only_ignores_switch(self) -> None:
        # A populated forecast-only widget has no current-conditions row.
        widget = {**self._WIDGET, "mode": "forecast"}
        assert render_dashboard([widget], self._config()) == render_dashboard(
            [{**widget, "show_sun_times": False}], self._config()
        )

    @pytest.mark.parametrize("card_style", ["none", "border", "left_bar"])
    @pytest.mark.parametrize("display_levels", [2, 16])
    def test_block_uses_right_edge_and_two_centered_rows(
        self, card_style: str, display_levels: int
    ) -> None:
        # Both rows share a left anchor inside the right-aligned block.
        widget = {**self._WIDGET, "card_style": card_style}
        img = render_to_image(
            [widget], self._config(display_levels=display_levels)
        )
        upper = content_bbox(img, 330, 10, 450, 50)
        lower = content_bbox(img, 330, 50, 450, 90)
        assert upper is not None and lower is not None
        assert abs(upper[0] - lower[0]) <= 2
        assert 445 <= max(upper[2], lower[2]) <= 450
        # The icon's 80-pixel box and the block have the same center.
        assert_vertically_centered(
            img, (10, 10, 90, 90), (330, 10, 450, 90), tolerance=3
        )
        assert_all_white(img, 330, 4, 448, 10)
        assert_all_white(img, 330, 90, 450, 92)

    def test_block_scales_with_weather_icon(self) -> None:
        # Doubling weather font_size doubles the whole sun block's height.
        small = render_to_image([self._WIDGET], self._config())
        large = render_to_image(
            [{**self._WIDGET, "font_size": 64, "w": 920}], self._config()
        )
        assert_scales_proportionally(
            small,
            large,
            (330, 10, 450, 90),
            (660, 20, 900, 180),
            expected_ratio=2,
        )

    @pytest.mark.parametrize("width", [240, 326, 380, 460])
    @pytest.mark.parametrize("time_format", ["12", "24"])
    def test_temperature_and_sun_times_do_not_overlap(
        self, width: int, time_format: str
    ) -> None:
        # A long negative sensor temperature leaves a clear column gap.
        widget = {
            **self._WIDGET,
            "w": width,
            "temperature_entity": "sensor.outdoor",
        }
        config = self._config(
            time_format=time_format,
            states={
                **self._DEFAULTS["states"],
                "sensor.outdoor": {
                    "state": "-123.4",
                    "attributes": {"unit_of_measurement": "°F"},
                },
            },
        )
        image = render_to_image([widget], config)
        root = ET.fromstring(render_widget_svg(widget, config))
        ns = {"svg": "http://www.w3.org/2000/svg"}
        block = root.find("svg:g[@class='sun-times']", ns)
        assert block is not None
        icon = block.find("svg:g", ns)
        weather_icon = root.find("svg:g/svg:svg", ns)
        assert icon is not None and weather_icon is not None
        transform = icon.attrib["transform"]
        left = int(transform.removeprefix("translate(").split(",")[0])
        height = int(weather_icon.attrib["height"])
        assert_all_white(image, left - 3, 10, left, 10 + height)
        assert_has_dark_pixels(image, 10 + height, 10, left - 3, 10 + height)
        assert_has_dark_pixels(
            image, left, 10, width - 10, ceil(10 + height / 2)
        )
        assert_has_dark_pixels(
            image, left, ceil(10 + height / 2), width - 10, 10 + height
        )

    @pytest.mark.parametrize(
        ("time_zone", "rising", "setting"),
        [
            ("Europe/Warsaw", "06:42", "17:28"),
            ("UTC", "04:42", "15:28"),
            ("invalid/zone", "04:42", "15:28"),
        ],
    )
    def test_local_hours_and_replacement(
        self, time_zone: str, rising: str, setting: str
    ) -> None:
        # Public SVG output contains local times and no old top-row values.
        svg = render_widget_svg(
            {**self._WIDGET, "mode": "full", "forecast_days": 0},
            self._config(time_zone=time_zone),
        )
        assert f">{rising}</text>" in svg
        assert f">{setting}</text>" in svg
        assert ">24°</text>" not in svg
        assert ">16°</text>" not in svg
        assert ">0mm</text>" not in svg
        root = ET.fromstring(svg)
        times = [e for e in root.iter() if e.text in (rising, setting)]
        assert len(times) == 2
        assert times[0].get("x") == times[1].get("x")
        assert all(e.get("text-anchor") == "start" for e in times)

    @pytest.mark.parametrize(
        ("date", "expected"),
        [("2026-01-23T04:42:00Z", "05:42"), ("2026-07-23T04:42:00Z", "06:42")],
    )
    def test_daylight_saving_time(self, date: str, expected: str) -> None:
        # The event date determines the UTC offset, not the current date.
        config = self._config(
            states={
                **MOCK_WEATHER_STATE,
                "sun.sun": {"attributes": {"next_rising": date}},
            }
        )
        assert f">{expected}</text>" in render_widget_svg(self._WIDGET, config)

    @pytest.mark.parametrize(
        ("time_format", "language", "expected"),
        [
            ("12", "pl", "5:28 PM"),
            ("24", "en-US", "17:28"),
            ("language", "pl", "17:28"),
            ("language", "en-US", "5:28"),
            ("system", "pl", "17:28"),
            ("24", "pl-XX", "17:28"),
            ("24", "123", "17:28"),
        ],
    )
    def test_time_format_and_language(
        self, time_format: str, language: str, expected: str
    ) -> None:
        # Explicit time formats win; language/system use the display locale.
        svg = render_widget_svg(
            self._WIDGET,
            self._config(time_format=time_format, language=language),
        )
        assert expected in svg

    @pytest.mark.parametrize("value", [None, "unavailable", "bad", 42])
    def test_invalid_time_uses_placeholder(self, value: object) -> None:
        # One invalid event retains its row while the other remains useful.
        config = self._config(
            states={
                **MOCK_WEATHER_STATE,
                "sun.sun": {
                    "attributes": {
                        "next_rising": value,
                        "next_setting": "2026-10-23T15:28:00Z",
                    }
                },
            }
        )
        svg = render_widget_svg(self._WIDGET, config)
        assert ">—</text>" in svg
        assert ">17:28</text>" in svg

    def test_missing_sun_keeps_both_placeholders(self) -> None:
        # Missing sun.sun does not restore forecast data or crash rendering.
        svg = render_widget_svg(
            self._WIDGET, self._config(states=MOCK_WEATHER_STATE)
        )
        assert svg.count(">—</text>") == 2

    def test_missing_weather_still_renders_nothing(self) -> None:
        # Sun data alone must not create a weather widget without its entity.
        image = render_to_image(
            [self._WIDGET], self._config(states={"sun.sun": MOCK_SUN_STATE})
        )
        assert_all_white(image, 0, 0, 1000, 500)
