# Laser Control Refactoring - Walkthrough

## Overview
This document describes the new modular architecture of the Laser Control application.

### Key Features
1.  **Offline/Demo Mode**: Runs without hardware (Mock Drivers).
2.  **Extensible Architecture**: 
    - `src/laser_control/drivers/base.py` defines the contract. 
    - Adding a new laser is as simple as subclassing `LaserDriver`.
3.  **Modern GUI**: built with `PySide6` and `PyQtGraph`.
4.  **Safe Save**: Data is autosaved to `data/autosaves` immediately.
5.  **Streaming & Sweep**: Hybrid driver handling both live streaming and triggered sweeps.

## Directory Structure
- `config/`: Contains `settings.toml`.
- `data/`: Autosaves.
- `src/laser_control/`: Source code.
    - `core/`: Logic engine.
    - `drivers/`: Hardware interface.
    - `gui/`: UI components.

## How to Run

### 1. Install Dependencies
Using `uv`:
```bash
uv sync
```
Or pip:
```bash
pip install -e .
```

### 2. Launch
```bash
uv run python src/laser_control/main.py
```
Or via the entry point:
```bash
uv run laser-control
```

## Testing Offline
1. Launch the app.
2. In the "Connection Dialog", check **"Use Mock Drivers (Offline Mode)"**.
3. Click OK.
4. Go to "Live Mode" -> "Start Live View" (You should see sine waves).
5. **New:** Use the "Laser Controls" panel to adjust Wavelength and Power. Try the **Dial** for fine-tuning!
6. Go to "Sweep Mode" -> "Start Sweep" (You should see a progress bar and a Lorentzian peak).

## Configuration
Edit `config/settings.toml` to add new GPIB addresses or default paths.
