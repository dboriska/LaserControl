from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Optional
import numpy as np


class InstrumentConnectionError(Exception):
    """Raised when an instrument fails to connect."""

    pass


class InstrumentDriver(ABC):
    """Base class for all instrument drivers."""

    def __init__(self):
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    def connect(self, config: Dict[str, Any]):
        """
        Connect to the instrument.

        Args:
            config: Dictionary containing connection parameters (address, ip, etc.)
        """
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the instrument and release resources."""
        pass


class LaserDriver(InstrumentDriver):
    """Abstract base class for Tunable Laser Sources."""

    @abstractmethod
    def set_wavelength(self, wavelength_nm: float):
        """Set the laser output wavelength."""
        pass

    @abstractmethod
    def set_power(self, power_dbm: float):
        """Set the laser output power."""
        pass

    @abstractmethod
    def set_sweep_params(self, start_nm: float, end_nm: float, speed_nm_s: float):
        """Configure the sweep parameters."""
        pass

    @abstractmethod
    def turn_on(self):
        """Turn the laser emission ON."""
        pass

    @abstractmethod
    def turn_off(self):
        """Turn the laser emission OFF."""
        pass

    @abstractmethod
    def start_sweep(self):
        """Start the wavelength sweep."""
        pass

    @abstractmethod
    def stop_sweep(self):
        """Stop/Abort the current sweep."""
        pass


class ScopeDriver(InstrumentDriver):
    """Abstract base class for Oscilloscopes."""

    @abstractmethod
    def configure_channels(self, channels: Dict[str, Dict]):
        """
        Configure channel settings.

        Args:
            channels: Dict like {'A': {'range': 5.0, 'coupling': 'DC', 'enabled': True}}
        """
        pass

    @abstractmethod
    def start_streaming(self, callback_func):
        """
        Start acquisition in streaming mode (Live View).

        Args:
            callback_func: Function to call with new data chunk.
        """
        pass

    @abstractmethod
    def stop_streaming(self):
        """Stop streaming acquisition."""
        pass

    @abstractmethod
    def capture_block(
        self, duration_s: float, sample_rate: float
    ) -> Dict[str, np.ndarray]:
        """
        Capture a single block of data (Sweep Mode).

        Args:
            duration_s: Time to capture in seconds.
            sample_rate: Sampling rate in Hz.

        Returns:
            Dict containing time array and channel data arrays.
        """
        pass
