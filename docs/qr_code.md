# QR Code widget

The **QR Code** widget creates a standard QR symbol locally. Select it in
the widget picker, choose **Text** or **Entity** as the content source,
and set its position and dimensions in **Layout**. The SVG preview and
dashboard PNG use the same server renderer; no external QR service or
network request is involved.

## Text source

Enter a URL, text, or an already formatted payload such as `WIFI:…` in
**QR content**. Whitespace and Unicode are preserved exactly. Jinja
templates are not evaluated. These examples are widget objects in the
dashboard's widget list, not Lovelace card configurations:

```yaml
type: qr_code
source: text
content: "https://example.org/guest"
title: "Guest information"
x: 24
y: 24
w: 240
h: 240
error_correction: M
```

For a guest Wi-Fi network, supply a correctly escaped Wi-Fi payload:

```yaml
type: qr_code
source: text
title: "Guest Wi-Fi"
content: "WIFI:T:WPA;S:Guest;P:example-password;;"
x: 24
y: 24
w: 240
h: 240
```

The encoded data is present in the dashboard image. Anyone who can view
the image, including via its public image endpoint, can scan the payload.
Use guest credentials when displaying Wi-Fi access information.

## Entity source

Select any Home Assistant entity. Leave **Attribute** empty to encode
its raw state, or enter an attribute name to encode that value instead.
The renderer does not add units or apply number/locale formatting.
Values are refreshed on the dashboard's existing refresh schedule and
manual refresh, rather than through a new QR-specific subscription.

```yaml
type: qr_code
source: entity
entity: sensor.guest_information
attribute: url
title: "Guest information"
x: 24
y: 24
w: 240
h: 240
```

Switching between sources in the editor preserves the inactive fields.
The optional **Title** is rendered above the symbol. **Label** and
**Description** are editor annotations and are not rendered.

## Size and readability

Width and height default to 200 pixels. The symbol remains square and
is centered in the available area below the title. It is black on an
opaque white background, with a four-module quiet zone on every side.
Only integer module sizes are used, with a minimum of three pixels per
module. Other widgets should not be placed over the symbol or its margin.

Longer payloads, a title, or stronger error correction can require a
larger widget. **Error correction** defaults to **M** and supports
**L**, **M**, **Q** and **H**. The chosen level is used exactly; it is
not automatically increased. The encoder selects the QR version.
Micro QR, logos, inverted colors and custom module shapes are not used.

Missing or unavailable entities, missing attributes, empty values,
oversized payloads and undersized viewports produce a placeholder inside
the widget. Other widgets continue to render. Increase the dimensions
or shorten the payload if prompted. Attributes must contain a scalar
value, rather than a list or mapping.

Tests decode the final PNG with an independent QR reader, including
Unicode, all correction levels, grayscale dithering and 90-degree
rotations. Scanning from a physical e-ink panel still depends on the
panel, refresh quality, lighting and camera; verify it on the device.
