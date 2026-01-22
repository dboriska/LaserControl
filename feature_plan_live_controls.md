# Feature Plan: Live Laser Controls

## Objective
Add interactive controls to the "Live Mode" tab allowing the user to adjust **Laser Power** and **Wavelength** in real-time while observing the oscilloscope stream.

## 1. User Interface Design (`LivePlotWidget`)

We will add a new **Control Toolbar** above the Plot, separate from the existing "Start/Stop" buttons.

### A. Wavelength Control Group
*   **Display**: A large `QDoubleSpinBox` for Wavelength input.
    *   *Range*: 1260nm - 1640nm (Hardware limits read from config).
    *   *Decimals*: 4 (0.0001 nm precision).
    *   *Suffix*: " nm".
*   **Precision Tuning (The "Arrow/Wheel" requirement)**:
    *   **Step Size Selector**: A set of Radio Buttons or a ComboBox to define the increment size.
        *   Options: `10 nm`, `1 nm`, `0.1 nm`, `0.01 nm`.
    *   **Interaction**:
        *   **Keyboard**: Up/Down arrows increment by the selected Step Size.
        *   **Mouse Wheel**: Scrolling over the spinbox increments by Step Size.
        *   **Dial/Knob (Optional)**: A `QDial` widget. Rotating it sends `+Step` or `-Step` events. This simulates a hardware knob.

### B. Power Control Group
*   **Display**: `QDoubleSpinBox`.
    *   *Range*: -20 dBm to +13 dBm.
    *   *Suffix*: " dBm".
*   **Logic**: Updates immediately on value change (with a small debounce to prevent flooding the GPIB bus during fast scrolling).

## 2. Architecture Updates

### A. Data Flow
1.  **`MainWindow`**:
    *   Must pass the `LaserDriver` instance (from `engine.laser`) to the `LivePlotWidget` during initialization or connection.
2.  **`LivePlotWidget`**:
    *   Stores a reference to `self.laser`.
    *   On `valueChanged` signal from inputs -> calls `self.laser.set_wavelength(val)`.

### B. Safety & State
*   **Connection State**: The controls must be **Disabled (Greyed out)** if the laser is not connected.
*   **Debouncing**: If the user spins the mouse wheel fast, we shouldn't send 50 commands per second to a physical instrument. We will use a `QTimer` (SingleShot) debounce mechanism (e.g., 100ms delay) before sending the command.

## 3. Implementation Steps

1.  **Refactor `LivePlotWidget`**:
    *   Update `__init__` to accept `laser_driver`.
    *   Create `setup_laser_controls()` method to build the UI.
2.  **Implement Step Logic**:
    *   Connect Radio Buttons to `spinbox.setSingleStep()`.
3.  **Implement Dial Logic (Bonus)**:
    *   Connect `QDial.valueChanged` -> Calculate Delta -> `spinbox.stepBy(delta)`.
4.  **Connect to Driver**:
    *   Implement the slot `update_hardware()`.
5.  **Update `MainWindow`**:
    *   Pass the real laser driver object after succesful connection.

## 4. Mockup (Code Structure)

```python
# Pseudo-code for Widget Layout
control_layout = QHBoxLayout()

# Wavelength
wl_group = QGroupBox("Wavelength")
wl_layout = QVBoxLayout()
self.wl_spin = QDoubleSpinBox()
self.wl_spin.setButtonSymbols(QAbstractSpinBox.NoButtons) # Cleaner look
self.wl_dial = QDial() # The "Wheel"
self.step_selector = QComboBox() 
self.step_selector.addItems(["1 nm", "0.1 nm", ...])

# Power
pwr_group = QGroupBox("Power")
self.pwr_spin = QDoubleSpinBox()

control_layout.addWidget(wl_group)
control_layout.addWidget(pwr_group)
```
