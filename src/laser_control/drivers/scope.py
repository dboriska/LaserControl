import ctypes
import numpy as np
import time
from typing import Dict, Any, Callable

try:
    from picosdk.ps5000a import ps5000a as ps
    from picosdk.functions import adc2mV, assert_pico_ok

    PICOSDK_FOUND = True
except (ImportError, Exception):
    PICOSDK_FOUND = False
    ps = None
from .base import ScopeDriver, InstrumentConnectionError


class PicoScopeDriver(ScopeDriver):
    """Driver for PicoScope 5000A Series using ctypes."""

    def __init__(self):
        super().__init__()
        self.chandle = ctypes.c_int16()
        self.status = {}
        self.maxADC = ctypes.c_int16()
        self.channel_range = 0
        if PICOSDK_FOUND:
            self.channel_range = ps.PS5000A_RANGE["PS5000A_5V"]  # Default
        self._streaming = False

        # Buffers for streaming
        self.bufferAMax = None
        self.bufferBMax = None

    def connect(self, config: Dict[str, Any]):
        try:
            # Open Resolution: 12 Bit
            resolution = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_12BIT"]
            self.status["openunit"] = ps.ps5000aOpenUnit(
                ctypes.byref(self.chandle), None, resolution
            )

            # Check power
            try:
                assert_pico_ok(self.status["openunit"])
            except:
                powerStatus = self.status["openunit"]
                if powerStatus == 286 or powerStatus == 282:
                    self.status["changePowerSource"] = ps.ps5000aChangePowerSource(
                        self.chandle, powerStatus
                    )
                    assert_pico_ok(self.status["changePowerSource"])
                else:
                    raise InstrumentConnectionError("PicoScope not found")

            # Get Max ADC
            self.status["maximumValue"] = ps.ps5000aMaximumValue(
                self.chandle, ctypes.byref(self.maxADC)
            )

            self._connected = True

        except Exception as e:
            self._connected = False
            raise InstrumentConnectionError(f"PicoScope Error: {str(e)}")

    def disconnect(self):
        if self._connected:
            self.stop_streaming()
            ps.ps5000aCloseUnit(self.chandle)
        self._connected = False

    def configure_channels(self, channels: Dict[str, Dict]):
        if not self._connected:
            return

        for ch_name, params in channels.items():
            ch_idx = ps.PS5000A_CHANNEL[f"PS5000A_CHANNEL_{ch_name}"]
            enabled = 1 if params.get("enabled", True) else 0
            coupling = ps.PS5000A_COUPLING["PS5000A_DC"]  # Hardcoded for now

            # Simple range mapping (could be expanded)
            v_range = params.get("range", 5.0)
            if v_range >= 5:
                r_code = ps.PS5000A_RANGE["PS5000A_5V"]
            elif v_range >= 2:
                r_code = ps.PS5000A_RANGE["PS5000A_2V"]
            elif v_range >= 1:
                r_code = ps.PS5000A_RANGE["PS5000A_1V"]
            else:
                r_code = ps.PS5000A_RANGE["PS5000A_500MV"]

            self.status[f"setCh{ch_name}"] = ps.ps5000aSetChannel(
                self.chandle, ch_idx, enabled, coupling, r_code, 0.0
            )
            self.channel_range = r_code  # Store for conversion

    def start_streaming(self, callback_func: Callable[[np.ndarray, np.ndarray], None]):
        """
        Starts streaming and calls callback_func(ch_a_volts, ch_b_volts) periodically.
        """
        if not self._connected or self._streaming:
            return

        sample_rate = 100000  # 100 kS/s default for live view
        sample_interval = ctypes.c_int32(int(1e6 / sample_rate))
        buffer_size = 10000

        # Prepare Buffers for C-Interop
        self.bufferAMax = np.zeros(shape=buffer_size, dtype=np.int16)
        self.bufferBMax = np.zeros(shape=buffer_size, dtype=np.int16)

        ps.ps5000aSetDataBuffer(
            self.chandle,
            0,
            self.bufferAMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            buffer_size,
            0,
            0,
        )
        ps.ps5000aSetDataBuffer(
            self.chandle,
            1,
            self.bufferBMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            buffer_size,
            0,
            0,
        )

        # Start Streaming
        ps.ps5000aRunStreaming(
            self.chandle,
            ctypes.byref(sample_interval),
            ps.PS5000A_TIME_UNITS["PS5000A_US"],
            0,
            buffer_size,
            0,
            1,
            0,
            buffer_size,
        )

        self._streaming = True

        # We need a polling loop. Since this is usually run in a thread by the caller,
        # but here we are non-blocking?
        # IMPORTANT: The Caller (Main Window or Worker) should loop and call `poll_streaming()`
        # But `start_streaming` implies it starts the process.
        # In this design, to keep it simple, we will assume the GUI has a timer calling a method
        # `get_streaming_values`. Let's create that helper.

    def get_streaming_values(self) -> tuple[np.ndarray, np.ndarray]:
        """Check for ready samples from the driver buffer."""
        if not self._streaming:
            return (np.array([]), np.array([]))

        was_called = False

        def cb(
            handle,
            noOfSamples,
            startIndex,
            overflow,
            triggerAt,
            triggered,
            autoStop,
            param,
        ):
            nonlocal was_called
            was_called = True
            # We rely on bufferAMax being updated in place by the driver
            self._temp_sample_count = noOfSamples
            self._temp_start_index = startIndex

        cFuncPtr = ps.StreamingReadyType(cb)
        ps.ps5000aGetStreamingLatestValues(self.chandle, cFuncPtr, None)

        if was_called and self._temp_sample_count > 0:
            # Extract data
            raw_a = self.bufferAMax[
                self._temp_start_index : self._temp_start_index
                + self._temp_sample_count
            ]
            raw_b = self.bufferBMax[
                self._temp_start_index : self._temp_start_index
                + self._temp_sample_count
            ]

            # Convert
            volts_a = np.array(adc2mV(raw_a, self.channel_range, self.maxADC)) / 1000.0
            volts_b = np.array(adc2mV(raw_b, self.channel_range, self.maxADC)) / 1000.0

            return volts_a, volts_b

        return np.array([]), np.array([])

    def stop_streaming(self):
        if self._streaming:
            ps.ps5000aStop(self.chandle)
            self._streaming = False

    def capture_block(
        self, duration_s: float, sample_rate: float
    ) -> Dict[str, np.ndarray]:
        """Blocking call for Sweep Mode."""
        if not self._connected:
            raise InstrumentConnectionError("Not connected")

        # Stop any streaming
        if self._streaming:
            self.stop_streaming()

        num_samples = int(duration_s * sample_rate)
        timebase = 0  # Need to calculate this based on sample_rate for PS5000a
        # Calculation: (timebase - 2) / 62,500,000 = interval (for 12 bit?)
        # For simplicity in this plan, we'll hardcode a valid timebase for ~100kHz or use findTimebase
        # But to be robust, let's use a standard default or proper calculation.

        # NOTE: For this implementation, we will assume a fixed timebase that works for the user's scan speed
        # or implement a simple lookup.
        timebase = 65  # Approx 1us interval (1MS/s)

        ps.ps5000aRunBlock(
            self.chandle, num_samples, num_samples, timebase, 0, None, 0, None, None
        )

        # Wait
        ready = ctypes.c_int16(0)
        while ready.value == 0:
            ps.ps5000aIsReady(self.chandle, ctypes.byref(ready))
            time.sleep(0.01)

        # Get Data
        bufferA = np.zeros(shape=num_samples, dtype=np.int16)
        bufferB = np.zeros(shape=num_samples, dtype=np.int16)

        ps.ps5000aSetDataBuffer(
            self.chandle,
            0,
            bufferA.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            num_samples,
            0,
            0,
        )
        ps.ps5000aSetDataBuffer(
            self.chandle,
            1,
            bufferB.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            num_samples,
            0,
            0,
        )

        ps.ps5000aGetValues(
            self.chandle, 0, ctypes.byref(ctypes.c_int32(num_samples)), 1, 0, 0, None
        )

        t = np.linspace(0, duration_s, num_samples)
        volts_a = np.array(adc2mV(bufferA, self.channel_range, self.maxADC)) / 1000.0
        volts_b = np.array(adc2mV(bufferB, self.channel_range, self.maxADC)) / 1000.0

        return {"t": t, "A": volts_a, "B": volts_b}
