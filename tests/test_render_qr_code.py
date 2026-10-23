"""Verify QR payloads and scan geometry through the public render pipeline."""

from __future__ import annotations

import pytest
import zxingcpp

from custom_components.eink_dashboard.svg_render import render_widget_svg
from tests.helpers import (
    assert_all_white,
    assert_has_dark_pixels,
    content_bbox,
    render_to_image,
)


class TestRenderQrCode:
    """Exercise readable QR codes and recoverable widget errors."""

    @pytest.mark.parametrize(
        "content",
        [
            "https://example.org/?a=1&b=2",
            "Zażółć gęślą jaźń 🏠",
            "WIFI:T:WPA;S:Guest;P:example-password;;",
            "  text with whitespace\n",
        ],
    )
    def test_payload_roundtrip(self, content: str) -> None:
        # An independent decoder must recover the exact original payload.
        img = render_to_image(
            [{"type": "qr_code", "content": content, "x": 0}],
            {"width": 200, "height": 200},
        )
        result = zxingcpp.read_barcode(img)
        assert result is not None
        assert result.text == content
        assert result.format == zxingcpp.BarcodeFormat.QRCode

    @pytest.mark.parametrize("level", ["L", "M", "Q", "H"])
    def test_correction_levels(self, level: str) -> None:
        # All supported correction levels produce a readable standard QR.
        img = render_to_image(
            [
                {
                    "type": "qr_code",
                    "content": "12345678",
                    "x": 0,
                    "error_correction": level,
                }
            ],
            {"width": 200, "height": 200},
        )
        result = zxingcpp.read_barcode(img)
        assert result is not None
        assert result.text == "12345678"
        assert result.ec_level == level

    def test_centering_and_quiet_zone(self) -> None:
        # A version-1 QR uses 21 modules plus four white modules per side.
        img = render_to_image(
            [
                {
                    "type": "qr_code",
                    "content": "12345678",
                    "x": 10,
                    "y": 20,
                    "w": 240,
                    "h": 200,
                }
            ],
            {"width": 260, "height": 240},
        )
        assert content_bbox(img, 0, 0, 260, 240) == (67, 57, 193, 183)
        assert_all_white(img, 43, 33, 217, 57)
        assert_all_white(img, 43, 183, 217, 207)
        assert_all_white(img, 43, 57, 67, 183)
        assert_all_white(img, 193, 57, 217, 183)
        assert set(img.get_flattened_data()) == {0, 255}

    def test_proportional_scaling(self) -> None:
        # Doubling the viewport doubles module size without interpolation.
        boxes = []
        for size in (145, 290):
            img = render_to_image(
                [
                    {
                        "type": "qr_code",
                        "content": "12345678",
                        "x": 0,
                        "w": size,
                        "h": size,
                    }
                ],
                {"width": size, "height": size},
            )
            boxes.append(content_bbox(img, 0, 0, size, size))
        assert boxes == [(20, 20, 125, 125), (40, 40, 250, 250)]

    def test_opaque_background(self) -> None:
        # Underlying content must not contaminate the quiet zone.
        img = render_to_image(
            [
                {
                    "type": "frame",
                    "x": 0,
                    "y": 0,
                    "w": 200,
                    "h": 200,
                    "fill_color": 0,
                },
                {"type": "qr_code", "content": "12345678", "x": 0},
            ],
            {"width": 200, "height": 200},
        )
        assert_all_white(img, 0, 0, 200, 37)
        result = zxingcpp.read_barcode(img)
        assert result is not None
        assert result.text == "12345678"

    @pytest.mark.parametrize(
        "attribute, expected", [(None, "8.41"), ("url", "https://example.org")]
    )
    def test_entity_source(self, attribute: str | None, expected: str) -> None:
        # Entity data is encoded verbatim, without units or locale formatting.
        img = render_to_image(
            [
                {
                    "type": "qr_code",
                    "source": "entity",
                    "x": 0,
                    "entity": "sensor.qr",
                    "attribute": attribute,
                    "content": "ignored",
                }
            ],
            {
                "width": 200,
                "height": 200,
                "number_format": "decimal_comma",
                "states": {
                    "sensor.qr": {
                        "state": "8.41",
                        "attributes": {
                            "url": "https://example.org",
                            "unit_of_measurement": "°C",
                        },
                    }
                },
            },
        )
        result = zxingcpp.read_barcode(img)
        assert result is not None
        assert result.text == expected

    @pytest.mark.parametrize("rotation", [0, 90, 180, 270])
    @pytest.mark.parametrize("levels", [2, 4, 16])
    def test_readable_after_optimization(
        self, rotation: int, levels: int
    ) -> None:
        # Decode the final PNG after dithering, quantization and rotation.
        img = render_to_image(
            [{"type": "qr_code", "content": "https://example.org", "x": 0}],
            {
                "width": 200,
                "height": 200,
                "optimize": True,
                "rotation": rotation,
                "display_levels": levels,
            },
        )
        result = zxingcpp.read_barcode(img.convert("L"))
        assert result is not None
        assert result.text == "https://example.org"

    @pytest.mark.parametrize(
        "fields, states, message",
        [
            ({"content": ""}, {}, "No QR content"),
            ({"content": "   "}, {}, "No QR content"),
            (
                {"source": "entity", "entity": "sensor.missing"},
                {},
                "Entity unavailable",
            ),
            (
                {"source": "entity", "entity": "sensor.qr"},
                {"sensor.qr": {"state": "unknown"}},
                "Entity unavailable",
            ),
            (
                {"source": "entity", "entity": "sensor.qr"},
                {"sensor.qr": {"state": "unavailable"}},
                "Entity unavailable",
            ),
            (
                {
                    "source": "entity",
                    "entity": "sensor.qr",
                    "attribute": "url",
                },
                {"sensor.qr": {"state": "ok", "attributes": {}}},
                "Attribute unavailable",
            ),
            ({"content": "x" * 10000}, {}, "QR content too long"),
            ({"content": "x" * 3000}, {}, "QR content too long"),
            ({"content": ["not", "scalar"]}, {}, "Invalid QR configuration"),
            (
                {"content": "12345678", "w": 86, "h": 86},
                {},
                "Enlarge widget or shorten content",
            ),
            (
                {"content": "test", "error_correction": "invalid"},
                {},
                "Invalid QR configuration",
            ),
            (
                {"source": "invalid", "content": "test"},
                {},
                "Invalid QR configuration",
            ),
        ],
    )
    def test_errors_are_local(
        self, fields: dict, states: dict, message: str
    ) -> None:
        # Expected data errors render feedback and leave other widgets intact.
        widget = {"type": "qr_code", "x": 0, **fields}
        config = {"width": 300, "height": 260, "states": states}
        svg = render_widget_svg(widget, config)
        assert message in svg
        img = render_to_image(
            [widget, {"type": "separator", "x": 0, "y": 240, "length": 100}],
            config,
        )
        assert zxingcpp.read_barcode(img) is None
        assert_has_dark_pixels(img, 0, 240, 100, 242)

    def test_title_is_escaped_and_does_not_overlap(self) -> None:
        # Untrusted titles stay text, above the reserved QR area.
        widget = {
            "type": "qr_code",
            "x": 0,
            "content": "12345678",
            "title": '<script>alert("x")</script>',
        }
        config = {"width": 200, "height": 200}
        svg = render_widget_svg(widget, config)
        assert "<script>" not in svg
        img = render_to_image([widget], config)
        assert_has_dark_pixels(img, 0, 0, 200, 28)
        result = zxingcpp.read_barcode(img)
        assert result is not None
        assert result.text == "12345678"

    def test_minimum_module_size(self) -> None:
        # Three pixels per module is accepted at the exact viewport boundary.
        img = render_to_image(
            [
                {
                    "type": "qr_code",
                    "x": 0,
                    "content": "12345678",
                    "w": 87,
                    "h": 87,
                }
            ],
            {"width": 87, "height": 87},
        )
        result = zxingcpp.read_barcode(img)
        assert result is not None
        assert result.text == "12345678"
