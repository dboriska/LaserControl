import pandas as pd
import numpy as np
import os
import time
from datetime import datetime

AUTOSAVE_DIR = os.path.join(os.getcwd(), "data", "autosaves")


class DataManager:
    """Handles data storage, auto-saving, and user export."""

    @staticmethod
    def ensure_autosave_dir():
        os.makedirs(AUTOSAVE_DIR, exist_ok=True)

    @staticmethod
    def autosave_sweep(wavelengths: np.ndarray, signal: np.ndarray) -> str:
        """
        Immediately save data to a temporary location.
        Returns the absolute path to the autosaved file.
        """
        DataManager.ensure_autosave_dir()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sweep_autosave_{timestamp}.csv"
        filepath = os.path.join(AUTOSAVE_DIR, filename)

        df = pd.DataFrame({"Wavelength_nm": wavelengths, "Amplitude_V": signal})

        try:
            df.to_csv(filepath, index=False)
            return filepath
        except Exception as e:
            print(f"Critical Autosave Error: {e}")
            return ""

    @staticmethod
    def move_autosave(autosave_path: str, target_dir: str, prefix: str) -> str:
        """
        Move the autosaved file to the user's desired location with a new name.
        """
        if not os.path.exists(autosave_path):
            raise FileNotFoundError("Original autosave file missing")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{prefix}_{timestamp}.csv"
        target_path = os.path.join(target_dir, new_filename)

        # Load and Save to new location (to ensure permissions etc)
        df = pd.read_csv(autosave_path)
        df.to_csv(target_path, index=False)

        # Cleanup original ONLY if successful
        os.remove(autosave_path)

        return target_path

    @staticmethod
    def discard_autosave(autosave_path: str):
        """Cleanup unwanted data."""
        if os.path.exists(autosave_path):
            os.remove(autosave_path)
