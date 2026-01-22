import time
import numpy as np
import threading
from typing import Dict, Any
from .base import LaserDriver, ScopeDriver


class MockLaserDriver(LaserDriver):
    """Fake laser for testing/offline mode."""

    def connect(self, config: Dict[str, Any]):
        print(f"[MOCK] Laser connecting with config: {config}")
        time.sleep(0.5)
        self._connected = True

    def disconnect(self):
        print("[MOCK] Laser disconnected")
        self._connected = False

    def set_wavelength(self, wavelength_nm: float):
        print(f"[MOCK] Setting wavelength to {wavelength_nm} nm")

    def set_power(self, power_dbm: float):
        print(f"[MOCK] Setting power to {power_dbm} dBm")

    def set_sweep_params(self, start_nm: float, end_nm: float, speed_nm_s: float):
        print(f"[MOCK] Sweep Conf: {start_nm}-{end_nm} nm @ {speed_nm_s} nm/s")

    def turn_on(self):
        print("[MOCK] Laser Emission ON")

    def turn_off(self):
        print("[MOCK] Laser Emission OFF")

    def start_sweep(self):
        print("[MOCK] Starting Sweep Trigger")

    def stop_sweep(self):
        print("[MOCK] Stopping Sweep")


class MockScopeDriver(ScopeDriver):
    """Fake scope generating sine waves."""

    def __init__(self):
        super().__init__()
        self._streaming = False
        self._stream_thread = None

    def connect(self, config: Dict[str, Any]):
        print("[MOCK] Scope Connected")
        self._connected = True

    def disconnect(self):
        self.stop_streaming()
        print("[MOCK] Scope Disconnected")
        self._connected = False

    def configure_channels(self, channels: Dict[str, Dict]):
        print(f"[MOCK] Configuring Channels: {channels}")

    def start_streaming(self, callback_func):
        if self._streaming:
            return

        print("[MOCK] Starting Streaming")
        self._streaming = True

        def runner():
            t_start = time.time()
            while self._streaming:
                # Generate fake 10ms chunks
                chunk_size = 1000
                t = np.linspace(0, 0.01, chunk_size)
                # Moving sine wave
                phase = (time.time() - t_start) * 10

                ch_a = np.sin(2 * np.pi * 50 * t + phase) + np.random.normal(
                    0, 0.1, chunk_size
                )
                ch_b = np.cos(2 * np.pi * 50 * t + phase) + np.random.normal(
                    0, 0.1, chunk_size
                )

                callback_func(ch_a, ch_b)
                time.sleep(0.01)  # 10ms wait

        self._stream_thread = threading.Thread(target=runner, daemon=True)
        self._stream_thread.start()

    def stop_streaming(self):
        self._streaming = False
        if self._stream_thread:
            self._stream_thread.join(timeout=1.0)
        print("[MOCK] Stopped Streaming")

    def capture_block(
        self, duration_s: float, sample_rate: float
    ) -> Dict[str, np.ndarray]:
        print(f"[MOCK] Capturing block: {duration_s}s @ {sample_rate}Hz")
        time.sleep(duration_s)  # Simulate acquisition time

        n_samples = int(duration_s * sample_rate)
        t = np.linspace(0, duration_s, n_samples)

        # Simulate a Lorentzian dip (absorption)
        center_t = duration_s / 2
        width = duration_s / 10
        signal = 1.0 - 0.5 * (width**2 / ((t - center_t) ** 2 + width**2))

        return {
            "t": t,
            "A": np.zeros(n_samples),  # Trigger
            "B": signal + np.random.normal(0, 0.01, n_samples),  # Signal
        }
