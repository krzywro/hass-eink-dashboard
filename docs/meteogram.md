# Meteogram

The Meteogram widget uses an hourly forecast from a Home Assistant
`weather` entity. It shows weather icons above a black temperature curve,
numeric temperatures below it, and optional precipitation bars and
cloud coverage. Below the chart are the hours, wind direction arrows,
and wind speeds with units.

Add **Meteogram** in the widget editor and choose an entity supporting
hourly forecasts. The default widget size is 400 × 280 pixels.

| Setting | Default | Purpose |
| --- | --- | --- |
| `entity` | Required | Weather entity with an hourly forecast |
| `hours` | `24` | Forecast window, limited to 8–120 hours |
| `show_temperature_labels` | `true` | Temperatures below the curve |
| `show_wind` | `true` | Wind arrows and speed below the hours |
| `show_precipitation` | `true` | Precipitation bars with amount labels |
| `show_cloud_cover` | `true` | Cloud coverage band above the curve |
| `show_hour_grid` | `true` | Dashed lines at full local hours |
| `show_y_axis_labels` | `true` | Numeric temperature scale on the Y axis |
| `card_style` | `none` | `none`, `border`, or `left_bar` decoration |

Forecast annotations use the same timestamps. They appear at least
three hours apart, with wider spacing for narrow widgets, long forecast
windows, or large text. The temperature curve and precipitation bars
continue to use every available forecast point. Hours and day boundaries
use Home Assistant's configured time zone. Numeric values use the display's
number-format preferences. Temperature and wind speed labels always round
to whole numbers, with no decimal places. Temperatures use the same scale
as the curve and are labeled with a degree symbol.

Temperature labels stay below the curve and clear of axis labels and
precipitation amounts. A label is omitted if it cannot fit inside the
plot. Increasing the widget's width or reducing the forecast window
allows more detail to be shown. Wind space is included within the
configured widget height.

The temperature curve is solid black for maximum contrast on e-ink.
Disable **Show Y-axis labels** (`show_y_axis_labels: false`) to hide the
numeric vertical scale. Horizontal grid lines and forecast temperature
labels remain available, and the hidden scale no longer reserves space
beside the first temperature label.

## Hourly grid, clouds, and precipitation

Vertical dashed grid lines mark every full local hour, independently of
the annotation spacing or missing forecast entries. The grid uses the
native light-gray palette level 170 (`#AAAAAA`) and stops above the hour
labels. Midnight uses the existing day separator without an extra stroke.
Clock changes preserve the actual order and spacing of forecast times.
Disable **Show hourly grid** (`show_hour_grid: false`) in the widget editor
to hide these lines. Day separators remain visible.

The cloud band uses a lighter tint, with 30% opacity on displays with
more than four grayscale levels. Four-level displays, including the
reTerminal E1001, use a sparse pattern of native light-gray pixels with
equivalent average brightness. This keeps the cloud band visible when
the four-level palette is applied with dithering disabled. The dashboard
does not change the device's dithering configuration.

Precipitation amounts are centered horizontally inside their bars and
aligned near the bottom with a small inset that scales with text size.
Labels are omitted when their text would not fit within the bar's width
or height. The bar itself keeps its true height, including light rainfall.

## Wind direction and units

**Arrowheads point where the air is moving.** A northerly wind, originating
from the north (`wind_bearing: 0` or `N`), points down. A westerly wind
(`270` or `W`) points right. Numeric azimuths and the 16 compass points
(`N`, `NNE`, `NE`, …) are supported.

Speed comes from each forecast entry's `wind_speed`, and its unit comes
from the weather entity's `wind_speed_unit`, such as `km/h`, `m/s`, or
`mph`. The widget preserves those units without converting them. Calm
wind shows zero with the unit and no arrow. A missing or invalid speed,
unit, or direction is shown as `—` for that component. Current weather
observations never replace missing forecast values.

The wind footer disappears when wind is disabled or the displayed
forecast contains no usable wind data, releasing that space to the chart.
Existing saved widgets receive both new features without a migration.
