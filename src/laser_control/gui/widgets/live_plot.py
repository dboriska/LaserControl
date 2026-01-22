from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QLabel
from PySide6.QtCore import QTimer, Slot
import pyqtgraph as pg
import numpy as np
from ...drivers.scope import ScopeDriver
from ...drivers.base import LaserDriver
from PySide6.QtWidgets import (
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QDoubleSpinBox,
    QDial,
    QLabel,
    QFrame,
)


class LivePlotWidget(QWidget):
    """
    Widget for real-time oscilloscope streaming.
    Adapts logic from PicoLive.py
    """

    def __init__(self, scope_driver: ScopeDriver, laser_driver: LaserDriver = None):
        super().__init__()
        self.scope = scope_driver
        self.laser = laser_driver
        self.is_streaming = False
        self.roll_buffer_size = 50000
        self.time_buffer = np.linspace(0, 5, self.roll_buffer_size)  # 5s window
        self.data_buffer_a = np.zeros(self.roll_buffer_size)
        self.data_buffer_b = np.zeros(self.roll_buffer_size)

        self.setup_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.setInterval(30)  # 30ms -> ~33fps

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. Laser Controls
        self.laser_controls = self.setup_laser_controls()
        layout.addWidget(self.laser_controls)

        # 2. Scope Controls
        ctrl_layout = QHBoxLayout()
        self.btn_toggle = QPushButton("Start Live View")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.toggled.connect(self.toggle_streaming)

        self.btn_auto = QPushButton("Auto Scale")
        self.btn_auto.clicked.connect(lambda: self.plot_item.enableAutoRange())

        ctrl_layout.addWidget(self.btn_toggle)
        ctrl_layout.addWidget(self.btn_auto)
        ctrl_layout.addStretch()

        layout.addLayout(ctrl_layout)

        # 3. Plot
        self.plot_widget = pg.PlotWidget()
        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.setTitle("Live Scope Monitor")
        self.plot_item.setLabel("bottom", "Time", "s")
        self.plot_item.setLabel("left", "Voltage", "V")
        self.plot_item.showGrid(x=True, y=True)

        self.curve_a = self.plot_item.plot(pen="y", name="Channel A")
        self.curve_b = self.plot_item.plot(pen="c", name="Channel B")

        layout.addWidget(self.plot_widget)

    def setup_laser_controls(self):
        frame = QGroupBox("Laser Controls")
        layout = QHBoxLayout(frame)

        # Power
        pwr_layout = QVBoxLayout()
        pwr_layout.addWidget(QLabel("Power (dBm):"))
        self.sb_power = QDoubleSpinBox()
        self.sb_power.setRange(-20, 13)
        self.sb_power.setDecimals(2)
        self.sb_power.setValue(0)
        self.sb_power.valueChanged.connect(self.set_power)
        pwr_layout.addWidget(self.sb_power)
        pwr_layout.addStretch()
        layout.addLayout(pwr_layout)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Wavelength
        wl_layout = QVBoxLayout()
        wl_layout.addWidget(QLabel("Wavelength (nm):"))

        self.sb_wavelength = QDoubleSpinBox()
        self.sb_wavelength.setRange(1260, 1640)
        self.sb_wavelength.setDecimals(4)
        self.sb_wavelength.setSingleStep(1.0)
        self.sb_wavelength.setSuffix(" nm")
        self.sb_wavelength.valueChanged.connect(self.set_wavelength)

        # Dial helper
        dial_layout = QHBoxLayout()
        self.dial = QDial()
        self.dial.setRange(0, 360)  # Infinite feel logic
        self.dial.setWrapping(True)
        self.dial.setNotchesVisible(True)
        self.dial.valueChanged.connect(self.on_dial_moved)
        self.last_dial_val = 0

        dial_layout.addWidget(self.sb_wavelength)
        dial_layout.addWidget(self.dial)

        wl_layout.addLayout(dial_layout)

        # Step Size
        step_frame = QGroupBox("Tuning Step")
        step_layout = QHBoxLayout(step_frame)
        self.step_group = QButtonGroup()

        for val, label in [
            (10.0, "10nm"),
            (1.0, "1nm"),
            (0.1, "0.1nm"),
            (0.01, "Fine"),
        ]:
            rb = QRadioButton(label)
            if val == 1.0:
                rb.setChecked(True)
            self.step_group.addButton(rb)
            rb.toggled.connect(
                lambda c, v=val: self.sb_wavelength.setSingleStep(v) if c else None
            )
            step_layout.addWidget(rb)

        wl_layout.addWidget(step_frame)
        layout.addLayout(wl_layout)

        # Initial Disable
        frame.setEnabled(False)
        return frame

    def set_power(self, val):
        if self.laser and self.laser.is_connected:
            try:
                self.laser.set_power(val)
            except:
                pass

    def set_wavelength(self, val):
        if self.laser and self.laser.is_connected:
            try:
                self.laser.set_wavelength(val)
            except:
                pass

    def on_dial_moved(self, val):
        """Simulate endless encoder."""
        delta = val - self.last_dial_val
        if delta > 180:
            delta -= 360  # Wrap forward
        if delta < -180:
            delta += 360  # Wrap backward

        if delta > 0:
            self.sb_wavelength.stepUp()
        elif delta < 0:
            self.sb_wavelength.stepDown()

        self.last_dial_val = val

    @Slot(bool)
    def toggle_streaming(self, active: bool):
        if active:
            if not self.scope.is_connected:
                self.btn_toggle.setChecked(False)
                return

            self.scope.start_streaming(
                None
            )  # Callback not used directly in driver logic I wrote, polling used
            self.is_streaming = True
            self.timer.start()
            self.btn_toggle.setText("Stop Live View")
        else:
            self.scope.stop_streaming()
            self.is_streaming = False
            self.timer.stop()
            self.btn_toggle.setText("Start Live View")

    def update_plot(self):
        if not self.is_streaming:
            return

        # Poll driver
        # Since I implemented `get_streaming_values` in scope.py:
        # If the driver was strictly callback based, we'd need a thread-safe queue.
        # But my driver implementation has a `get_streaming_values` helper.
        # Wait, I need to check `scope.py` again.
        # Yes, I added `get_streaming_values`.

        if hasattr(self.scope, "get_streaming_values"):
            new_a, new_b = self.scope.get_streaming_values()

            if len(new_a) > 0:
                # Roll buffers
                n = len(new_a)
                if n > self.roll_buffer_size:
                    # Reset if too much data (lag)
                    self.data_buffer_a[:] = 0
                    self.data_buffer_b[:] = 0
                else:
                    self.data_buffer_a = np.roll(self.data_buffer_a, -n)
                    self.data_buffer_b = np.roll(self.data_buffer_b, -n)
                    self.data_buffer_a[-n:] = new_a
                    self.data_buffer_b[-n:] = new_b

                self.curve_a.setData(
                    self.time_buffer[-20000:], self.data_buffer_a[-20000:]
                )  # Just show last 2s for perf
                self.curve_b.setData(
                    self.time_buffer[-20000:], self.data_buffer_b[-20000:]
                )
