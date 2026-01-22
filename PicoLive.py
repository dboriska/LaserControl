import sys
import json
import numpy as np
import ctypes
from pyqtgraph.Qt import QtWidgets, QtCore
import pyqtgraph as pg
import os

# PicoScope imports
from picosdk.ps5000a import ps5000a as ps
from picosdk.functions import adc2mV, assert_pico_ok

# === Load config from JSON ===
default_config = {
    "start_with_ch1": True,
    "start_with_ch2": True,
    "start_with_autoscale": True,
    "start_fullscreen": False,
}

CONFIG_PATH = "config.json"

if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to read config.json, using defaults. Error: {e}")
        config = default_config
else:
    print("⚠️ config.json not found, using defaults.")
    config = default_config

# === Acquisition Parameters ===
SAMPLE_RATE = 10000  # 10 kHz
SLICE_MS = 10
SLICE_SAMPLES = int(SAMPLE_RATE * SLICE_MS / 1000)
ROLL_SECONDS = 5
ROLL_SAMPLES = SAMPLE_RATE * ROLL_SECONDS
TIME_VECTOR = np.linspace(0, ROLL_SECONDS, ROLL_SAMPLES, endpoint=False)
NUM_CHANNELS = 2


class RollingMultiChannelPlot:
    def __init__(self):
        # PicoScope initialization
        self.chandle = ctypes.c_int16()
        self.status = {}

        # Open PicoScope 5000 Series device
        # Resolution set to 12 Bit
        resolution = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_12BIT"]
        self.status["openunit"] = ps.ps5000aOpenUnit(
            ctypes.byref(self.chandle), None, resolution
        )

        # Handle power source changes
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
                raise RuntimeError("PicoScope 5000 Series not found or failed to open.")

        print("✅ PicoScope 5000A connected successfully")

        # Channel setup parameters
        enabled = 1
        disabled = 0
        coupling_type = ps.PS5000A_COUPLING["PS5000A_DC"]
        self.channel_range = ps.PS5000A_RANGE["PS5000A_5V"]
        analogue_offset = 0.0

        # Setup Channel A (CH1)
        self.status["setChA"] = ps.ps5000aSetChannel(
            self.chandle,
            ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"],
            enabled,
            coupling_type,
            self.channel_range,
            analogue_offset,
        )
        assert_pico_ok(self.status["setChA"])

        # Setup Channel B (CH2)
        self.status["setChB"] = ps.ps5000aSetChannel(
            self.chandle,
            ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"],
            enabled,
            coupling_type,
            self.channel_range,
            analogue_offset,
        )
        assert_pico_ok(self.status["setChB"])

        # Get maximum ADC value for conversion
        self.maxADC = ctypes.c_int16()
        self.status["maximumValue"] = ps.ps5000aMaximumValue(
            self.chandle, ctypes.byref(self.maxADC)
        )
        assert_pico_ok(self.status["maximumValue"])

        # Set up streaming mode
        # For ps5000a, sample interval is specified directly in the runStreaming call
        # Sample interval in microseconds
        self.sample_interval = ctypes.c_int32(
            int(1e6 / SAMPLE_RATE)
        )  # Convert Hz to µs interval

        print(
            f"📊 Requested sample interval: {self.sample_interval.value} µs ({SAMPLE_RATE} Hz)"
        )

        # Allocate buffers for streaming
        self.bufferAMax = np.zeros(shape=SLICE_SAMPLES * 100, dtype=np.int16)
        self.bufferBMax = np.zeros(shape=SLICE_SAMPLES * 100, dtype=np.int16)

        # Set data buffers
        memory_segment = 0
        self.status["setDataBuffersA"] = ps.ps5000aSetDataBuffer(
            self.chandle,
            ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"],
            self.bufferAMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            SLICE_SAMPLES * 100,
            memory_segment,
            ps.PS5000A_RATIO_MODE["PS5000A_RATIO_MODE_NONE"],
        )
        assert_pico_ok(self.status["setDataBuffersA"])

        self.status["setDataBuffersB"] = ps.ps5000aSetDataBuffer(
            self.chandle,
            ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"],
            self.bufferBMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            SLICE_SAMPLES * 100,
            memory_segment,
            ps.PS5000A_RATIO_MODE["PS5000A_RATIO_MODE_NONE"],
        )
        assert_pico_ok(self.status["setDataBuffersB"])

        # Start streaming
        sampleUnits = ps.PS5000A_TIME_UNITS["PS5000A_US"]  # Microseconds
        maxPreTriggerSamples = 0
        maxPostPreTriggerSamples = SLICE_SAMPLES * 100
        autoStopOn = 0  # Keep streaming continuously
        downSampleRatio = 1

        self.status["runStreaming"] = ps.ps5000aRunStreaming(
            self.chandle,
            ctypes.byref(self.sample_interval),
            sampleUnits,
            maxPreTriggerSamples,
            maxPostPreTriggerSamples,
            autoStopOn,
            downSampleRatio,
            ps.PS5000A_RATIO_MODE["PS5000A_RATIO_MODE_NONE"],
            SLICE_SAMPLES * 100,
        )
        assert_pico_ok(self.status["runStreaming"])

        print(
            f"📊 Streaming started at actual interval: {self.sample_interval.value} µs"
        )

        # Rolling buffers for display
        self.buffers = [np.zeros(ROLL_SAMPLES) for _ in range(NUM_CHANNELS)]
        self.curves = []
        self.active_channels = [
            config.get("start_with_ch1", True),
            config.get("start_with_ch2", True),
        ]
        self.colors = ["y", "c"]
        self.auto_scale_enabled = config.get("start_with_autoscale", True)
        self.fullscreen = config.get("start_fullscreen", False)

        # Create PyQtGraph GUI
        self.app = QtWidgets.QApplication([])
        self.win = pg.GraphicsLayoutWidget(title="PicoScope Multi-Channel Scope")

        if self.fullscreen:
            self.win.showFullScreen()
        else:
            self.win.show()

        self.plot = self.win.addPlot()
        self.plot.setTitle(
            "Live Signal (PicoScope 5000A)\nKeyboard: 1=CH1, 2=CH2, A=AutoScale, F=Fullscreen, Q=Quit"
        )
        self.plot.setXRange(0, ROLL_SECONDS)
        self.plot.enableAutoRange("x", False)
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setLabel("left", "Voltage (V)")
        self.plot.setYRange(-5, 5)
        self.plot.enableAutoRange("y", self.auto_scale_enabled)

        for ch in range(NUM_CHANNELS):
            self.curves.append(self.plot.plot(pen=self.colors[ch]))

        self.win.keyPressEvent = self.handle_keypress

        # Timer for updating plot
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.read_and_plot)
        self.timer.start(SLICE_MS)

        # Track if we're still acquiring
        self.was_called_back = False

    def handle_keypress(self, event):
        key = event.key()
        # Handle both PyQt5 (QtCore.Qt.Key_X) and PyQt6 (QtCore.Qt.Key.Key_X)
        try:
            Key_1 = QtCore.Qt.Key_1
            Key_2 = QtCore.Qt.Key_2
            Key_A = QtCore.Qt.Key_A
            Key_F = QtCore.Qt.Key_F
            Key_Q = QtCore.Qt.Key_Q
        except AttributeError:
            # PyQt6 style
            Key_1 = QtCore.Qt.Key.Key_1
            Key_2 = QtCore.Qt.Key.Key_2
            Key_A = QtCore.Qt.Key.Key_A
            Key_F = QtCore.Qt.Key.Key_F
            Key_Q = QtCore.Qt.Key.Key_Q

        if key == Key_1:
            self.active_channels[0] = not self.active_channels[0]
            print(f"Channel 1: {'ON' if self.active_channels[0] else 'OFF'}")
        elif key == Key_2:
            self.active_channels[1] = not self.active_channels[1]
            print(f"Channel 2: {'ON' if self.active_channels[1] else 'OFF'}")
        elif key == Key_A:
            self.auto_scale_enabled = not self.auto_scale_enabled
            if self.auto_scale_enabled:
                self.plot.enableAutoRange("y", True)
                print("🔄 Y-axis auto-scale: ENABLED")
            else:
                self.plot.enableAutoRange("y", False)
                self.plot.setYRange(-5, 5)
                print("📏 Y-axis auto-scale: DISABLED")
        elif key == Key_F:
            if self.fullscreen:
                self.win.showNormal()
                self.fullscreen = False
                print("⏹️ Exited fullscreen mode.")
            else:
                self.win.showFullScreen()
                self.fullscreen = True
                print("🖥️ Entered fullscreen mode.")
        elif key == Key_Q:
            print("👋 Exiting application...")
            self.cleanup()
            self.app.quit()

    def read_and_plot(self):
        # Check for new data
        self.was_called_back = False

        def streaming_callback(
            handle,
            noOfSamples,
            startIndex,
            overflow,
            triggerAt,
            triggered,
            autoStop,
            param,
        ):
            self.was_called_back = True
            self.noOfSamples = noOfSamples
            self.startIndex = startIndex

        # Create callback function pointer
        cFuncPtr = ps.StreamingReadyType(streaming_callback)

        # Get latest values
        self.status["getStreamingLastestValues"] = ps.ps5000aGetStreamingLatestValues(
            self.chandle, cFuncPtr, None
        )

        if self.was_called_back:
            # Convert ADC counts to mV, then to V
            ch_a_mv = adc2mV(
                self.bufferAMax[: self.noOfSamples], self.channel_range, self.maxADC
            )
            ch_b_mv = adc2mV(
                self.bufferBMax[: self.noOfSamples], self.channel_range, self.maxADC
            )

            # Convert mV list to V numpy array
            new_data_a = np.array(ch_a_mv) / 1000.0
            new_data_b = np.array(ch_b_mv) / 1000.0

            # Limit to SLICE_SAMPLES
            samples_to_use = min(self.noOfSamples, SLICE_SAMPLES)

            # Update Channel A
            if self.active_channels[0]:
                self.buffers[0] = np.roll(self.buffers[0], -samples_to_use)
                self.buffers[0][-samples_to_use:] = new_data_a[:samples_to_use]
                self.curves[0].setData(TIME_VECTOR, self.buffers[0])
            else:
                self.curves[0].setData([], [])

            # Update Channel B
            if self.active_channels[1]:
                self.buffers[1] = np.roll(self.buffers[1], -samples_to_use)
                self.buffers[1][-samples_to_use:] = new_data_b[:samples_to_use]
                self.curves[1].setData(TIME_VECTOR, self.buffers[1])
            else:
                self.curves[1].setData([], [])

    def cleanup(self):
        """Stop streaming and close the device"""
        try:
            self.status["stop"] = ps.ps5000aStop(self.chandle)
            self.status["close"] = ps.ps5000aCloseUnit(self.chandle)
            print("🔌 PicoScope disconnected")
        except:
            pass

    def run(self):
        try:
            # Handle both PyQt5 and PyQt6 / PySide compatibility
            app_instance = QtWidgets.QApplication.instance()
            if hasattr(app_instance, "exec"):
                app_instance.exec()
            else:
                app_instance.exec_()
        finally:
            self.cleanup()


if __name__ == "__main__":
    try:
        app = RollingMultiChannelPlot()
        app.run()
    except Exception as e:
        print("ERROR:", e)
        import traceback

        traceback.print_exc()
