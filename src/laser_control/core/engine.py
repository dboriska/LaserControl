from PySide6.QtCore import QObject, Signal, QThread
import time
import numpy as np
from typing import Dict, Any

from ..drivers.base import LaserDriver, ScopeDriver
from ..drivers.laser import SantecLaserDriver
from ..drivers.scope import PicoScopeDriver
from ..drivers.mocks import MockLaserDriver, MockScopeDriver
from ..utils.data_manager import DataManager


class SweepWorker(QThread):
    """Background thread for performing the wavelength sweep."""

    data_ready = Signal(object, object)  # wavelengths, signal
    status_update = Signal(str)
    finished_safe = Signal(str)  # Path to autosave
    error_occurred = Signal(str)

    def __init__(self, laser: LaserDriver, scope: ScopeDriver, params: Dict[str, Any]):
        super().__init__()
        self.laser = laser
        self.scope = scope
        self.params = params
        self._is_running = True

    def run(self):
        try:
            start_nm = self.params["start_nm"]
            end_nm = self.params["end_nm"]
            speed = self.params["speed_nm_s"]
            power = self.params["power_dbm"]

            # 1. Configure Laser
            self.status_update.emit("Configuring Laser...")
            self.laser.set_power(power)
            self.laser.set_sweep_params(start_nm, end_nm, speed)

            # 2. Configure Scope (Calculate duration)
            duration = abs(end_nm - start_nm) / speed
            # Add margin
            duration += 0.5

            # 3. Arm Systems
            self.status_update.emit("Arming Trigger...")
            self.laser.turn_on()
            time.sleep(0.5)  # Warm up

            # 4. Start Capture (Blocking Scope / Non-blocking Laser)
            # We need to start Scope capture *before* Laser sweep to catch the trigger
            # BUT scope capture is blocking in our driver currently.
            # So we launch laser sweep in a separate short thread or rely on hardware trigger order.

            # Standard Protocol:
            # A. Laser Enabled, Trigger Out ready.
            # B. Scope waits for Trigger (Block Mode).
            # C. Laser Starts Sweep.

            # Since scope.capture_block() is blocking and waits for trigger...
            # We need to trigger the laser *after* calling capture_block? No, capture_block blocks this thread.
            # So we must use a helper thread to start the laser?
            # OR, picosdk has RunBlock (Async) -> IsReady (Loop) -> GetValues.
            # Our `capture_block` in `scope.py` does the loop.
            # We need to modify the flow:
            #   i. Start Scope (Async)
            #   ii. Start Laser
            #   iii. Wait for Scope

            # Since I implemented `capture_block` as atomic blocking, I should fix it or work around it.
            # Workaround: Launch laser start in timer/thread just before capture.

            import threading

            def trigger_laser():
                time.sleep(0.5)  # Give scope time to arm
                self.laser.start_sweep()

            trigger_thread = threading.Thread(target=trigger_laser)

            self.status_update.emit("Acquiring...")
            trigger_thread.start()

            # BLOCKING CALL - Waits for trigger and duration
            data = self.scope.capture_block(
                duration, 100000
            )  # 100 kS/s default for sweep

            trigger_thread.join()
            self.laser.stop_sweep()
            self.laser.turn_off()

            # 5. Process Data
            self.status_update.emit("Processing...")

            # Map Time -> Wavelength
            # Lambda(t) = Start + Speed * t (Assuming linear)
            # We need to find t=0 (Trigger point).
            # In Block mode with trigger, t[0] is roughly trigger point.

            time_axis = data["t"]
            signal = data["B"]

            wavelengths = start_nm + (time_axis * speed)

            # Clip to range
            mask = (wavelengths >= start_nm) & (wavelengths <= end_nm)

            # Autosave
            self.status_update.emit("Saving...")
            path = DataManager.autosave_sweep(wavelengths[mask], signal[mask])

            self.data_ready.emit(wavelengths[mask], signal[mask])
            self.finished_safe.emit(path)

        except Exception as e:
            self.error_occurred.emit(str(e))
            try:
                self.laser.stop_sweep()
            except:
                pass


class MeasurementEngine(QObject):
    """Manages hardware connections and worker threads."""

    def __init__(self):
        super().__init__()
        self.laser = None
        self.scope = None

        # Load Defaults
        self.mock_mode = False

    def initialize_drivers(
        self, laser_config: Dict, scope_config: Dict, force_mock=False
    ):
        """Initialize or Re-initialize drivers."""
        # Cleanup old
        if self.laser:
            self.laser.disconnect()
        if self.scope:
            self.scope.disconnect()

        if force_mock:
            self.laser = MockLaserDriver()
            self.scope = MockScopeDriver()
            self.mock_mode = True
        else:
            self.laser = SantecLaserDriver()
            self.scope = PicoScopeDriver()
            self.mock_mode = False

        # Connect
        try:
            self.laser.connect(laser_config)
            self.scope.connect(scope_config)
            return True, "Connected successfully"
        except Exception as e:
            # Fallback to mock if failed? Or let GUI decide.
            # For now, return Error.
            return False, str(e)

    def start_sweep(self, params):
        worker = SweepWorker(self.laser, self.scope, params)
        return worker
