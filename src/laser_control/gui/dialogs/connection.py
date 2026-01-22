from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QDialogButtonBox,
    QLabel,
    QCheckBox,
)
from ...utils.config import load_settings


class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect Instruments")
        self.settings = load_settings()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Laser Section
        layout.addWidget(QLabel("<b>Laser Configuration</b>"))
        form = QFormLayout()

        self.cb_laser_presets = QComboBox()
        self.populate_presets()
        self.cb_laser_presets.currentIndexChanged.connect(self.on_preset_changed)

        self.chk_mock = QCheckBox("Use Mock Drivers (Offline Mode)")

        form.addRow("Preset:", self.cb_laser_presets)
        form.addRow("", self.chk_mock)

        layout.addLayout(form)

        # Connection Details Display (Read-only for now, extensibility point)
        self.lbl_details = QLabel("Select a preset...")
        layout.addWidget(self.lbl_details)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.on_preset_changed(0)  # Init

    def populate_presets(self):
        presets = (
            self.settings.get("instruments", {}).get("laser", {}).get("presets", [])
        )
        for p in presets:
            self.cb_laser_presets.addItem(p.get("name", "Unknown"), p)

    def on_preset_changed(self, index):
        data = self.cb_laser_presets.currentData()
        if data:
            if data["interface"] == "GPIB":
                txt = f"Interface: GPIB\nAddress: {data.get('address')}"
            else:
                txt = f"Interface: LAN\nIP: {data.get('ip')}:{data.get('port')}"
            self.lbl_details.setText(txt)

    def get_config(self):
        """Returns (laser_config, scope_config, use_mock)"""
        use_mock = self.chk_mock.isChecked()
        laser_conf = self.cb_laser_presets.currentData() or {}

        # Scope defaults from settings
        scope_conf = self.settings.get("instruments", {}).get("scope", {})

        return laser_conf, scope_conf, use_mock
