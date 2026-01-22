import os
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QToolBar,
    QStatusBar,
    QMessageBox,
    QLabel,
    QDoubleSpinBox,
    QPushButton,
    QFileDialog,
    QLineEdit,
    QComboBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon

from ..core.engine import MeasurementEngine
from .widgets.live_plot import LivePlotWidget
from .widgets.sweep_plot import SweepPlotWidget
from .dialogs.connection import ConnectionDialog
from ..utils.config import get_last_working_dir, set_last_working_dir
from ..utils.data_manager import DataManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laser Control v2.0")
        self.resize(1200, 800)

        self.engine = MeasurementEngine()
        self.sweep_worker = None

        self.setup_ui()
        self.show_connection_dialog()  # Auto-show on startup

    def setup_ui(self):
        # 1. Toolbar
        self.toolbar = QToolBar("Main")
        self.addToolBar(self.toolbar)

        action_connect = QAction("Connect", self)
        action_connect.triggered.connect(self.show_connection_dialog)
        self.toolbar.addAction(action_connect)

        action_fullscreen = QAction("Fullscreen", self)
        action_fullscreen.triggered.connect(self.toggle_fullscreen)
        self.toolbar.addAction(action_fullscreen)

        # 2. Central Widget (Tabs)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_live = QWidget()
        self.setup_live_tab()
        self.tabs.addTab(self.tab_live, "Live Mode")

        self.tab_sweep = QWidget()
        self.setup_sweep_tab()
        self.tabs.addTab(self.tab_sweep, "Sweep Mode")

        # 3. Status Bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    def setup_live_tab(self):
        layout = QVBoxLayout(self.tab_live)
        # Create without driver first? No, we need driver.
        # We will update the driver instance later.
        # But widget needs it in init.
        # Trick: Pass the engine and let widget ask engine for driver, or update widget.
        # For now, pass a dummy/None and update later.

        # Actually, let's defer creation until connection?
        # Better: Create a placeholder or init with Mock.

        # Re-using MockDriver for init
        from ..drivers.mocks import MockScopeDriver

        self.live_widget = LivePlotWidget(MockScopeDriver())  # Placeholder
        layout.addWidget(self.live_widget)

    def setup_sweep_tab(self):
        layout = QHBoxLayout(self.tab_sweep)

        # Left: Controls
        ctrl_panel = QWidget()
        ctrl_panel.setFixedWidth(300)
        ctrl = QVBoxLayout(ctrl_panel)

        # Params
        ctrl.addWidget(QLabel("<b>Sweep Parameters</b>"))

        self.sb_start = self.create_spinbox(1520, 1400, 1650, "Start Wavelength (nm)")
        ctrl.addWidget(QLabel("Start (nm):"))
        ctrl.addWidget(self.sb_start)

        self.sb_end = self.create_spinbox(1570, 1400, 1650, "End Wavelength (nm)")
        ctrl.addWidget(QLabel("End (nm):"))
        ctrl.addWidget(self.sb_end)

        self.sb_speed = self.create_spinbox(10, 0.1, 100, "Speed (nm/s)")
        ctrl.addWidget(QLabel("Speed (nm/s):"))
        ctrl.addWidget(self.sb_speed)

        self.sb_power = self.create_spinbox(10, -20, 20, "Power (dBm)")
        ctrl.addWidget(QLabel("Power (dBm):"))
        ctrl.addWidget(self.sb_power)

        # Toggle Scan Mode (Placeholder)
        ctrl.addWidget(QLabel("Scan Mode:"))
        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["One-Way Scan", "Continuous (Future)"])
        ctrl.addWidget(self.cb_mode)

        # File Settings
        ctrl.addWidget(QLabel("<b>File Settings</b>"))
        self.le_prefix = QLineEdit("scan")
        ctrl.addWidget(QLabel("File Prefix:"))
        ctrl.addWidget(self.le_prefix)

        self.btn_dir = QPushButton("Set Save Directory")
        self.btn_dir.clicked.connect(self.choose_directory)
        ctrl.addWidget(self.btn_dir)
        self.lbl_dir = QLabel(get_last_working_dir() or os.getcwd())
        self.lbl_dir.setWordWrap(True)
        ctrl.addWidget(self.lbl_dir)

        ctrl.addStretch()

        self.btn_sweep = QPushButton("START SWEEP")
        self.btn_sweep.setMinimumHeight(50)
        self.btn_sweep.setStyleSheet(
            "background-color: darkgreen; color: white; font-weight: bold;"
        )
        self.btn_sweep.clicked.connect(self.run_sweep)
        ctrl.addWidget(self.btn_sweep)

        # Right: Plot
        self.sweep_plot = SweepPlotWidget()

        layout.addWidget(ctrl_panel)
        layout.addWidget(self.sweep_plot)

    def create_spinbox(self, val, min_v, max_v, tooltip):
        sb = QDoubleSpinBox()
        sb.setRange(min_v, max_v)
        sb.setValue(val)
        sb.setToolTip(tooltip)
        return sb

    def show_connection_dialog(self):
        dlg = ConnectionDialog(self)
        if dlg.exec():
            laser_conf, scope_conf, use_mock = dlg.get_config()

            success, msg = self.engine.initialize_drivers(
                laser_conf, scope_conf, force_mock=use_mock
            )

            if success:
                self.status.showMessage(f"Connected ({'MOCK' if use_mock else 'REAL'})")
                # Update Live Widget with real drivers
                self.live_widget.scope = self.engine.scope
                self.live_widget.laser = self.engine.laser
                # Enable controls
                self.live_widget.laser_controls.setEnabled(True)
            else:
                QMessageBox.critical(self, "Connection Failed", msg)
                self.status.showMessage("Connection Failed")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def choose_directory(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.lbl_dir.text()
        )
        if d:
            self.lbl_dir.setText(d)
            set_last_working_dir(d)  # Persist

    def run_sweep(self):
        if self.sweep_worker and self.sweep_worker.isRunning():
            return

        params = {
            "start_nm": self.sb_start.value(),
            "end_nm": self.sb_end.value(),
            "speed_nm_s": self.sb_speed.value(),
            "power_dbm": self.sb_power.value(),
        }

        self.btn_sweep.setEnabled(False)
        self.status.showMessage("Running Sweep...")

        self.sweep_worker = self.engine.start_sweep(params)
        self.sweep_worker.data_ready.connect(self.sweep_plot.set_data)
        self.sweep_worker.status_update.connect(self.status.showMessage)
        self.sweep_worker.error_occurred.connect(
            lambda e: QMessageBox.warning(self, "Error", e)
        )

        # Handle Saved File
        self.sweep_worker.finished_safe.connect(self.on_sweep_finished)
        self.sweep_worker.finished.connect(lambda: self.btn_sweep.setEnabled(True))

        self.sweep_worker.start()

    def on_sweep_finished(self, autosave_path):
        """Called when thread emits 'finished_safe'."""
        if not autosave_path:
            return

        # Prompt user
        prefix = self.le_prefix.text()
        target_dir = self.lbl_dir.text()

        try:
            final_path = DataManager.move_autosave(autosave_path, target_dir, prefix)
            self.status.showMessage(f"Saved to: {os.path.basename(final_path)}")
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))
