import time
import pyvisa
from typing import Dict, Any
from .base import LaserDriver, InstrumentConnectionError


class SantecLaserDriver(LaserDriver):
    """Driver for Santec TSL-550/710 Tunable Lasers."""

    def __init__(self):
        super().__init__()
        self.resource = None
        self.rm = None

    def connect(self, config: Dict[str, Any]):
        """
        Connect via GPIB or LAN.

        Config expects:
        - interface: "GPIB" or "LAN"
        - address: (GPIB only) e.g. "GPIB0::10::INSTR"
        - ip: (LAN only) e.g. "192.168.1.100"
        - port: (LAN only) e.g. 5000
        """
        try:
            self.rm = pyvisa.ResourceManager()

            if config.get("interface") == "LAN":
                ip = config["ip"]
                port = config["port"]
                resource_str = f"TCPIP0::{ip}::{port}::SOCKET"
                self.resource = self.rm.open_resource(
                    resource_str, read_termination="\r"
                )
                self.resource.timeout = 5000  # 5s timeout for LAN
            else:
                # Default to GPIB
                address = config.get("address", "GPIB0::10::INSTR")
                self.resource = self.rm.open_resource(address)

            # Verify identity
            idn = self.resource.query("*IDN?")
            print(f"Connected to Laser: {idn.strip()}")

            # Initial setup
            self.resource.write(":WAVelength:UNIT 0")  # nm
            self._connected = True

        except Exception as e:
            self._connected = False
            if self.resource:
                self.resource.close()
            raise InstrumentConnectionError(
                f"Failed to connect to Santec Laser: {str(e)}"
            )

    def disconnect(self):
        if self.resource:
            try:
                self.stop_sweep()
                self.turn_off()
                self.resource.close()
            except:
                pass
        self._connected = False

    def set_wavelength(self, wavelength_nm: float):
        if not self._connected:
            return
        self.resource.write(f":WAVelength {wavelength_nm:.4f}")

    def set_power(self, power_dbm: float):
        if not self._connected:
            return
        self.resource.write(
            f":POWer:ATT {power_dbm:.2f}"
        )  # Note: Santec uses attenuation logic often, or direct power. Keeping consistent with user's code using ATT/POW.
        # However, user code used :POW:ATT. Wait, standard is :POW <val> usually.
        # Checking santec.py: user used :POW:ATT for setAttenuation.
        # But for setPower? The old code used :POW <val>dBm.
        # Let's stick to :POW for target power control if the laser supports APC.
        self.resource.write(f":POWe {power_dbm:.2f}")

    def set_sweep_params(self, start_nm: float, end_nm: float, speed_nm_s: float):
        if not self._connected:
            return
        self.resource.write(f":WAV:SWE:START {start_nm:.4f}")
        self.resource.write(f":WAV:SWE:STOP {end_nm:.4f}")
        self.resource.write(f":WAV:SWE:SPE {speed_nm_s:.1f}")
        self.resource.write(":WAV:SWE:MOD 1")  # Continuous/One-way
        self.resource.write(":TRIG:OUTP 2")  # Trigger out enabled

    def turn_on(self):
        if not self._connected:
            return
        self.resource.write(":POWer:STATe 1")
        self.resource.write(":POW:SHUT 0")  # Open shutter

    def turn_off(self):
        if not self._connected:
            return
        self.resource.write(":POW:SHUT 1")  # Close shutter
        self.resource.write(":POWer:STATe 0")

    def start_sweep(self):
        if not self._connected:
            return
        self.resource.write(":WAV:SWE 1")

    def stop_sweep(self):
        if not self._connected:
            return
        self.resource.write(":WAV:SWE 0")
