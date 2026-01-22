import sys
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QGridLayout,
    QFrame,
    QSplitter,
    QRadioButton,
    QButtonGroup,
    QDoubleSpinBox,
    QFileDialog,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import matplotlib

matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.widgets import SpanSelector
import numpy as np
import pyvisa
import time
from picoscope import ps5000a
from datetime import datetime
import pandas as pd
from lmfit.models import SplineModel, LorentzianModel, ConstantModel


class InstrumentManager:
    def __init__(self):
        self.ps = None
        self.laser = None
        self.is_connected = False

    def connect_instruments(self):
        try:
            # Connect to PicoScope
            if self.ps is None:
                self.ps = ps5000a.PS5000a()
                time.sleep(0.2)
                self.ps.setResolution("12")
                self.ps.setChannel(
                    "A",
                    coupling="DC",
                    VRange=5,
                    VOffset=0.0,
                    enabled=True,
                    BWLimited=False,
                )
                self.ps.setChannel(
                    "B",
                    coupling="DC",
                    VRange=2,
                    VOffset=0.0,
                    enabled=True,
                    BWLimited=False,
                )

            # Connect to Laser
            if self.laser is None:
                rm = pyvisa.ResourceManager()
                self.laser = rm.open_resource("GPIB0::10::INSTR")

            self.is_connected = True
            return "Connected to both instruments successfully"
        except Exception as e:
            self.disconnect_instruments()
            raise Exception(f"Failed to connect: {str(e)}")

    def configure_for_sweep(self, params):
        try:
            # Configure PicoScope
            time_window = (
                params["end_wavelength"] - params["start_wavelength"]
            ) / params["sweep_speed"]
            sampling_interval = time_window / params["num_samples"]
            (actual_interval, num_samples, _) = self.ps.setSamplingInterval(
                sampling_interval, time_window
            )
            self.ps.setSimpleTrigger(
                trigSrc="A",
                threshold_V=1,
                direction="Rising",
                timeout_ms=int(10000),
                enabled=True,
            )

            # Configure Laser
            self.laser.write(f":WAV:SWE:START {params['start_wavelength']}nm")
            self.laser.write(f":WAV:SWE:STOP {params['end_wavelength']}nm")
            self.laser.write(f":POW {params['power']}dBm")
            self.laser.write(":WAV:SWE:MOD 1")
            self.laser.write(f":WAV:SWE:SPE {params['sweep_speed']}")
            self.laser.write(":TRIG:OUTP 2")

            return actual_interval, num_samples
        except Exception as e:
            raise Exception(f"Failed to configure instruments: {str(e)}")

    def configure_for_live(self, wavelength, power):
        try:
            # Configure PicoScope for continuous acquisition
            self.ps.setSimpleTrigger(
                trigSrc="A",
                threshold_V=1,
                direction="Rising",
                timeout_ms=1000,
                enabled=False,
            )

            # Configure Laser for CW operation
            self.laser.write(":WAV:SWE:MOD 0")
            self.laser.write(f":WAV {wavelength}nm")
            self.laser.write(f":POW {power}dBm")

        except Exception as e:
            raise Exception(f"Failed to configure for live mode: {str(e)}")

    def start_laser(self):
        if self.laser:
            self.laser.write(":POW:STAT 1")

    def stop_laser(self):
        if self.laser:
            self.laser.write(":POW:STAT 0")

    def get_data(self, num_samples):
        if not self.ps:
            raise Exception("PicoScope not connected")

        self.ps.runBlock()
        self.ps.waitReady()
        data_a = self.ps.getDataV("A", num_samples)
        data_b = self.ps.getDataV("B", num_samples)
        return data_a, data_b

    def disconnect_instruments(self):
        try:
            if self.ps:
                self.ps.stop()
                self.ps.close()
                self.ps = None

            if self.laser:
                self.laser.write(":POW:STAT 0")
                self.laser.close()
                self.laser = None

            self.is_connected = False
        except Exception as e:
            print(f"Error during disconnect: {str(e)}")


class SweepThread(QThread):
    finished = pyqtSignal(tuple)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, instrument_manager, params):
        super().__init__()
        self.instrument_manager = instrument_manager
        self.params = params
        self._stop = False

    def run(self):
        try:
            actual_interval, num_samples = self.instrument_manager.configure_for_sweep(
                self.params
            )
            self.status.emit("Starting sweep...")

            self.instrument_manager.start_laser()
            time.sleep(0.5)
            self.instrument_manager.laser.write(":WAV:SWE 1")

            _, data_b = self.instrument_manager.get_data(num_samples)
            self.instrument_manager.stop_laser()

            time_axis = np.arange(len(data_b)) * actual_interval
            wavelengths = (
                self.params["start_wavelength"] + time_axis * self.params["sweep_speed"]
            )
            mask = wavelengths <= self.params["end_wavelength"]
            wavelengths = wavelengths[mask]
            spectrum = data_b[: len(wavelengths)]

            self.finished.emit((wavelengths, spectrum))

        except Exception as e:
            self.error.emit(str(e))


class LiveDataThread(QThread):
    data_ready = pyqtSignal(np.ndarray, np.ndarray)
    error = pyqtSignal(str)

    def __init__(self, instrument_manager):
        super().__init__()
        self.instrument_manager = instrument_manager
        self._stop = False

    def run(self):
        try:
            # Configure sampling for live mode - using direct parameters
            samp_interval = 0.001  # 1ms sampling interval
            duration = 0.1  # 100ms duration
            (actual_interval, num_samples, _) = (
                self.instrument_manager.ps.setSamplingInterval(samp_interval, duration)
            )

            while not self._stop:
                data_a, data_b = self.instrument_manager.get_data(num_samples)
                self.data_ready.emit(data_a, data_b)
                time.sleep(0.1)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop = True


class LaserControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laser Control and Analysis")
        self.setGeometry(100, 100, 1200, 800)

        self.instrument_manager = InstrumentManager()
        self.setup_ui()

        # Initialize connection
        try:
            status = self.instrument_manager.connect_instruments()
            self.log_status(status)
        except Exception as e:
            self.log_status(f"Initial connection failed: {str(e)}")

        self.wavelengths = None
        self.spectrum = None
        self.is_running = False

        self.time_data = []
        self.channel_a_data = []
        self.channel_b_data = []
        self.last_plot_time = time.time()
        self.plot_window = 30  # seconds

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        control_panel = self.create_control_panel()
        plot_panel = self.create_plot_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(plot_panel)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def create_control_panel(self):
        panel = QFrame()
        panel.setFrameStyle(QFrame.Panel | QFrame.Raised)
        layout = QVBoxLayout(panel)

        # Mode selection
        mode_frame = QFrame()
        mode_layout = QHBoxLayout(mode_frame)
        self.mode_group = QButtonGroup(self)

        self.sweep_mode = QRadioButton("Sweep Mode")
        self.live_mode = QRadioButton("Live Power")
        self.sweep_mode.setChecked(True)

        self.mode_group.addButton(self.sweep_mode)
        self.mode_group.addButton(self.live_mode)

        mode_layout.addWidget(self.sweep_mode)
        mode_layout.addWidget(self.live_mode)
        layout.addWidget(mode_frame)

        self.sweep_mode.toggled.connect(self.mode_changed)

        # Parameters grid
        params_grid = QGridLayout()

        self.params = {}
        self.sweep_params = ["start_wavelength", "end_wavelength", "sweep_speed"]
        param_defaults = {
            "start_wavelength": (1480.0, "Start Wavelength (nm)"),
            "end_wavelength": (1620.0, "End Wavelength (nm)"),
            "power": (10, "Power (dBm)"),  # Make sure 'power' is included here
            "sweep_speed": (20.0, "Sweep Speed (nm/s)"),
            "num_samples": (1000000.0, "Number of Samples"),
        }

        row = 0
        for param, (default, label) in param_defaults.items():
            params_grid.addWidget(QLabel(label), row, 0)
            line_edit = QLineEdit(str(default))
            self.params[param] = (
                line_edit  # This line creates the 'power' entry in self.params
            )
            params_grid.addWidget(line_edit, row, 1)
            row += 1

        # Add wavelength spinbox after the other parameters
        params_grid.addWidget(QLabel("Live Wavelength (nm):"), row, 0)
        self.wavelength_spinbox = QDoubleSpinBox()
        self.wavelength_spinbox.setRange(1490.0000, 1640.0000)  # Full range
        self.wavelength_spinbox.setValue(1550.0000)
        self.wavelength_spinbox.setDecimals(4)
        self.wavelength_spinbox.setSingleStep(1)  # Default step
        self.wavelength_spinbox.setEnabled(False)
        self.wavelength_spinbox.setKeyboardTracking(False)
        self.wavelength_spinbox.setStepType(
            QDoubleSpinBox.DefaultStepType
        )  # Changed to default
        self.wavelength_spinbox.setAlignment(Qt.AlignRight)
        self.wavelength_spinbox.editingFinished.connect(self.on_wavelength_changed)
        params_grid.addWidget(self.wavelength_spinbox, row, 1)

        # Add buttons for different step sizes
        wavelength_buttons = QHBoxLayout()
        step_sizes = [("Fine: 0.1", 0.1), ("Medium: 1.0", 1.0), ("Coarse: 10.0", 10.0)]
        self.step_group = QButtonGroup(self)

        for label, step in step_sizes:
            btn = QRadioButton(label)
            wavelength_buttons.addWidget(btn)
            self.step_group.addButton(btn)
            # Fix the lambda to properly capture the step value
            btn.clicked.connect(lambda checked, s=step: self.change_step_size(s))

        self.step_group.buttons()[0].setChecked(True)  # Set Fine as default
        params_grid.addLayout(wavelength_buttons, row + 1, 0, 1, 2)

        # Connect signals after all widgets are created
        self.params["power"].textChanged.connect(self.update_laser_settings)
        self.wavelength_spinbox.valueChanged.connect(self.update_laser_settings)

        layout.addLayout(params_grid)

        self.action_button = QPushButton("Start Sweep")
        self.action_button.clicked.connect(self.start_action)
        layout.addWidget(self.action_button)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)

        layout.addStretch()
        return panel

    def change_step_size(self, step):
        self.wavelength_spinbox.setSingleStep(step)
        self.log_status(f"Step size changed to {step} nm")

    def on_wavelength_changed(self):
        if self.is_running and not self.sweep_mode.isChecked():
            try:
                wavelength = self.wavelength_spinbox.value()
                if 1520 <= wavelength <= 1570:
                    self.instrument_manager.configure_for_live(
                        wavelength, float(self.params["power"].text())
                    )
                    self.log_status(f"Wavelength manually set to {wavelength:.4f} nm")
            except Exception as e:
                self.log_status(f"Error setting wavelength: {str(e)}")

    def create_plot_panel(self):
        panel = QFrame()
        panel.setFrameStyle(QFrame.Panel | QFrame.Raised)
        layout = QVBoxLayout(panel)

        self.fig, (self.ax1, self.ax2) = plt.subplots(2, figsize=(8, 6))
        self.canvas = FigureCanvasQTAgg(self.fig)

        # Create large text display for live values
        self.live_text = plt.figtext(
            0.5, 0.02, "", fontsize=12, horizontalalignment="center"
        )

        for ax in [self.ax1, self.ax2]:
            ax.set_xlabel("Wavelength [nm]")
            ax.set_ylabel("Amplitude [V]")
            ax.grid(True)

        self.ax1.set_title("Press left mouse button and drag to select a region")

        (self.line2,) = self.ax2.plot([], [])
        (self.fitplot,) = self.ax2.plot([], [])

        self.toolbar = NavigationToolbar2QT(self.canvas, panel)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.span = SpanSelector(
            self.ax1,
            self.on_select,
            "horizontal",
            useblit=True,
            props=dict(alpha=0.5, facecolor="tab:blue"),
            interactive=True,
            drag_from_anywhere=True,
        )

        self.calc_q_button = QPushButton("Calculate Q")
        self.calc_q_button.clicked.connect(self.calculate_q)
        self.calc_q_button.setEnabled(False)
        layout.addWidget(self.calc_q_button)

        return panel

    def mode_changed(self):
        is_sweep = self.sweep_mode.isChecked()

        if self.is_running:
            if not is_sweep:
                self.stop_live_power()
            self.is_running = False

        # Enable/disable appropriate controls
        for param in self.sweep_params:
            self.params[param].setEnabled(is_sweep)
        self.wavelength_spinbox.setEnabled(not is_sweep)  # Enable in live mode

        self.calc_q_button.setEnabled(is_sweep and self.wavelengths is not None)
        self.action_button.setText("Start Sweep" if is_sweep else "Start Live Power")
        self.action_button.setEnabled(True)

        self.ax1.clear()
        self.ax2.clear()
        self.live_text.set_text("")

        if is_sweep:
            self.ax1.set_xlabel("Wavelength [nm]")
            self.ax1.set_ylabel("Amplitude [V]")
            self.ax2.set_visible(True)
            self.live_text.set_visible(False)
            self.ax1.set_visible(True)
        else:
            # Setup for live plotting
            self.ax2.set_visible(False)
            self.live_text.set_visible(True)
            self.ax1.set_visible(True)
            self.ax1.set_xlabel("Time [s]")
            self.ax1.set_ylabel("Voltage [V]")
            self.time_data = []
            self.channel_a_data = []
            self.channel_b_data = []
            self.last_plot_time = time.time()

        self.canvas.draw()

    def start_action(self):
        if self.sweep_mode.isChecked():
            self.start_sweep()
        else:
            self.start_live_power()

    def update_plot(self):
        self.ax1.clear()
        self.ax1.plot(self.wavelengths, self.spectrum)
        self.ax1.set_xlabel("Wavelength [nm]")
        self.ax1.set_ylabel("Amplitude [V]")
        self.ax1.grid(True)
        self.ax1.set_title("Press left mouse button and drag to select a region")
        self.canvas.draw()

    def on_select(self, xmin, xmax):
        if self.wavelengths is None:
            return

        indmin, indmax = np.searchsorted(self.wavelengths, (xmin, xmax))
        indmax = min(len(self.wavelengths) - 1, indmax)

        region_x = self.wavelengths[indmin:indmax]
        region_y = self.spectrum[indmin:indmax]

        if len(region_x) >= 2:
            self.line2.set_data(region_x, region_y)
            self.ax2.set_xlim(region_x[0], region_x[-1])
            self.ax2.set_ylim(region_y.min() * 0.9, region_y.max() * 1.1)
            self.canvas.draw()

    def calculate_q(self):
        if not hasattr(self, "line2") or len(self.line2.get_xdata()) < 2:
            self.log_status("Please select a region first")
            return

        try:
            region_x = self.line2.get_xdata()
            region_y = self.line2.get_ydata()

            numElems = 10
            idx = np.linspace(0, len(region_y) - 1, numElems).astype(int)
            xguess = region_x[idx]

            bkg = SplineModel(prefix="bkg_", xknots=xguess)
            lmodel = LorentzianModel() + ConstantModel() + bkg

            x_center_guess = region_x[np.argmin(region_y)]
            amplitude_guess = np.abs(np.max(region_y) - np.min(region_y))

            params = lmodel.make_params(
                amplitude=amplitude_guess,
                center=x_center_guess,
                sigma=0.01,
                c=np.max(region_y),
            )
            params.update(bkg.guess(region_y, region_x))

            result = lmodel.fit(region_y, params, x=region_x)

            Q_factor = int(
                np.round(result.params["center"].value / result.params["fwhm"].value)
            )
            df = np.round(
                3e8
                * (
                    result.params["fwhm"].value
                    * 1e-9
                    / (result.params["center"].value * 1e-9) ** 2
                )
            )

            self.ax2.clear()
            self.ax2.grid(True)
            self.ax2.set_xlabel("Wavelength [nm]")
            self.ax2.set_ylabel("Amplitude [V]")

            self.ax2.plot(
                region_x, region_y, "go", markeredgecolor="black", label="data"
            )
            xfine = np.linspace(region_x.min(), region_x.max(), 500)
            fit_y = result.eval(x=xfine)
            self.ax2.plot(
                xfine,
                fit_y,
                label=f"fit\nQ = {Q_factor}\nΔf = {self.human_format(df)}Hz",
            )
            self.ax2.legend()
            self.canvas.draw()

            self.log_status(f"Q factor: {Q_factor}")
            self.log_status(f"Delta f: {self.human_format(df)}Hz")

        except Exception as e:
            self.log_status(f"Error in Q calculation: {str(e)}")

    def start_sweep(self):
        if self.is_running:
            return

        try:
            sweep_params = {
                name: float(widget.text()) for name, widget in self.params.items()
            }

            self.action_button.setEnabled(False)
            self.is_running = True

            self.sweep_thread = SweepThread(self.instrument_manager, sweep_params)
            self.sweep_thread.finished.connect(self.sweep_completed)
            self.sweep_thread.error.connect(self.handle_error)
            self.sweep_thread.status.connect(self.log_status)
            self.sweep_thread.start()

        except Exception as e:
            self.log_status(f"Error: {str(e)}")
            self.action_button.setEnabled(True)
            self.is_running = False

    def start_live_power(self):
        if self.is_running:
            self.stop_live_power()
            return

        try:
            # Configure instruments for live mode
            self.instrument_manager.configure_for_live(
                self.wavelength_spinbox.value(), float(self.params["power"].text())
            )
            self.instrument_manager.start_laser()

            self.log_status("Instruments configured successfully")

            self.is_running = True
            self.action_button.setText("Stop Live Power")

            # Start data acquisition
            self.live_thread = LiveDataThread(self.instrument_manager)
            self.live_thread.data_ready.connect(self.update_live_data)
            self.live_thread.error.connect(self.handle_error)
            self.live_thread.start()

            self.log_status("Live monitoring started")

        except Exception as e:
            self.log_status(f"Error: {str(e)}")
            self.stop_live_power()

    def stop_live_power(self):
        self.is_running = False
        if hasattr(self, "live_thread"):
            self.live_thread.stop()
            self.live_thread.wait()
        self.instrument_manager.stop_laser()
        self.action_button.setText("Start Live Power")

    def update_live_data(self, data_a, data_b):
        current_time = time.time()
        if not hasattr(self, "start_time"):
            self.start_time = current_time

        self.time_data.append(current_time - self.start_time)
        self.channel_a_data.append(data_a[-1])
        self.channel_b_data.append(data_b[-1])

        # Simple text display of current values
        text = f"Channel A: {data_a[-1]:.4f} V    Channel B: {data_b[-1]:.4f} V"
        self.live_text.set_text(text)

        if not hasattr(self, "value_history"):
            self.value_history = {"A": [], "B": []}

        self.value_history["A"].append(data_a[-1])
        self.value_history["B"].append(data_b[-1])

        if len(self.value_history["A"]) > 10:
            self.value_history["A"].pop(0)
            self.value_history["B"].pop(0)

        avg_a = np.mean(self.value_history["A"])
        avg_b = np.mean(self.value_history["B"])
        std_a = np.std(self.value_history["A"])
        std_b = np.std(self.value_history["B"])

        stats = f"\n\nAvg A: {avg_a:.4f} V ± {std_a:.4f}\nAvg B: {avg_b:.4f} V ± {std_b:.4f}"
        self.live_text.set_text(text + stats)

        # Update plot if 10 seconds have passed
        if current_time - self.last_plot_time >= self.plot_window:
            self.time_data = []
            self.channel_a_data = []
            self.channel_b_data = []
            self.last_plot_time = current_time
            self.start_time = current_time

        # Plot data
        self.ax1.clear()
        self.ax1.plot(self.time_data, self.channel_a_data, label="Channel A")
        self.ax1.plot(self.time_data, self.channel_b_data, label="Channel B")
        self.ax1.set_xlabel("Time [s]")
        self.ax1.set_ylabel("Voltage [V]")
        self.ax1.grid(True)
        self.ax1.legend()
        self.canvas.draw()

    def sweep_completed(self, data):
        self.wavelengths, self.spectrum = data
        self.update_plot()
        self.action_button.setEnabled(True)
        self.calc_q_button.setEnabled(True)
        self.is_running = False

        # Save data to CSV
        try:
            # Create default filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"laser_sweep_{timestamp}.csv"

            # Open file dialog
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save Sweep Data",
                default_filename,
                "CSV Files (*.csv);;All Files (*)",
            )

            if filename:  # If user didn't cancel
                # Create DataFrame and save to CSV
                df = pd.DataFrame(
                    {"Wavelength_nm": self.wavelengths, "Amplitude_V": self.spectrum}
                )
                df.to_csv(filename, index=False)
                self.log_status(f"Data saved successfully to {filename}")
        except Exception as e:
            self.log_status(f"Error saving data: {str(e)}")

    def log_status(self, message):
        self.status_text.append(message)

    @staticmethod
    def human_format(num):
        num = float("{:.3g}".format(num))
        magnitude = 0
        while abs(num) >= 1000:
            magnitude += 1
            num /= 1000.0
        return "{}{}".format(
            "{:f}".format(num).rstrip("0").rstrip("."),
            ["", "K", "M", "G", "T"][magnitude],
        )

    def handle_error(self, error_msg):
        self.log_status(f"Error: {error_msg}")
        self.action_button.setEnabled(True)
        self.is_running = False
        if hasattr(self, "live_thread"):
            self.stop_live_power()

    def update_laser_settings(self):
        if (
            self.instrument_manager.is_connected
            and self.is_running
            and not self.sweep_mode.isChecked()
        ):
            try:
                wavelength = self.wavelength_spinbox.value()
                # Use power from spinbox
                power = float(self.params["power"].text())
                self.instrument_manager.laser.write(f":POW {power}dBm")
                self.log_status(f"Power set to {power} dBm")
            except Exception as e:
                self.log_status(f"Error updating power settings: {str(e)}")

    def closeEvent(self, event):
        if hasattr(self, "live_thread") and self.live_thread.isRunning():
            self.live_thread.stop()
            self.live_thread.wait()
        self.instrument_manager.disconnect_instruments()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LaserControlGUI()
    window.show()
    sys.exit(app.exec_())
