# Configuration Documentation (`settings.toml`)

This file (`config/settings.toml`) controls the application's default behavior, instrument connections, and UI preferences. It uses the TOML format.

## General Settings
```toml
[general]
last_working_directory = "/path/to/last/save"
default_file_prefix = "scan"
auto_save_enabled = true
```
*   `last_working_directory`: The folder where data was last saved. Updated automatically by the app.
*   `default_file_prefix`: The default text to appear in the "File Prefix" box.
*   `auto_save_enabled`: If `true`, runs data is always saved to `data/autosaves/` before prompting the user.

## Instrument Configuration
### Laser (`[instruments.laser]`)
Contains a list of presets for different laser connections.

```toml
[instruments.laser]
last_used_index = 0  # The index of the preset to select by default (0-based)

[[instruments.laser.presets]]
name = "Santec TSL-550 (GPIB)"
interface = "GPIB"
address = "GPIB0::10::INSTR"

[[instruments.laser.presets]]
name = "Santec Remote (LAN)"
interface = "LAN"
ip = "192.168.1.10"
port = 5000
```
*   **Presets**: You can add multiple `[[instruments.laser.presets]]` blocks.
*   `name`: Display name in the Connection Dialog dropdown.
*   `interface`: "GPIB" or "LAN".
*   `address`: VISA address string (Required if interface is GPIB).
*   `ip`: IP Address (Required if interface is LAN).
*   `port`: TCP Port (Required if interface is LAN).

### Oscilloscope (`[instruments.scope]`)
Configuration for the PicoScope or valid scope driver.

```toml
[instruments.scope]
model = "PS5000A"
resolution_bits = 12
channels = ["A", "B"]
```
*   `model`: Identifier for the driver to load (Currently supports "PS5000A").
*   `resolution_bits`: Hardware resolution setting (8, 12, 14, 15, 16 depending on model).
*   `channels`: List of active channels to enable on startup.

## UI Settings
```toml
[ui]
theme = "dark"
fullscreen_startup = false
```
*   `theme`: "dark" or "light" (Changes plot colors and window style).
*   `fullscreen_startup`: If `true`, the app launches in Fullscreen mode.
