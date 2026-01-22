# Laser Control Refactoring & Improvement Plan (v7: Complete)

This plan outlines the steps to modernize the `LaserConrtolOLD.py` script into a robust, maintainable, and user-friendly Python application. The new project will be managed using `uv` for dependency management and `git` for version control.

## 1. Technology Stack

*   **Manager**: `uv`
*   **GUI**: `PySide6`
*   **Plotting**: `pyqtgraph`
*   **Drivers**: `pyvisa`, `picosdk`, `santec` (adapted) + **Mock Drivers**

## 2. Architecture & Directory Structure

```text
laser-control/
├── pyproject.toml
├── config/
│   ├── config.json      # UI Theme
│   └── settings.toml    # Last Used Path, Instrument addresses
├── src/
│   ├── laser_control/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── engine.py
│   │   │   └── state.py
│   │   ├── drivers/
│   │   │   ├── base.py      # Abstract Base Class
│   │   │   ├── mocks.py     # Dummy Laser/Scope for offline mode
│   │   │   ├── laser.py
│   │   │   └── scope.py
│   │   ├── gui/
│   │   │   ├── main_window.py
│   │   │   ├── widgets/
│   │   │       ├── properties_panel.py # Scan Mode, File Prefix
│   │   │       └── ...
│   │   └── utils/ ...
```

## 3. Key Feature Improvements

### A. Offline / Demo Mode
*   **Requirement**: Program must start without hardware.
*   **Implementation**:
    *   On startup, try to connect to hardware define in `settings.toml`.
    *   If connection fails (or is disabled), auto-load `MockLaserDriver` and `MockScopeDriver`.
    *   **Mock Drivers**: Simulate behavior (e.g., return random noise for scope data, accept commands log them to console) so the UI remains fully functional for testing/demo.
    *   **Visual Indicator**: Status bar shows "OFFLINE MODE" in orange.

### B. Future-Proofing: Scan Modes
*   **UI Addition**: A Toggle Switch / Dropdown in the Control Panel.
    *   Options: `One-Way Sweep` (Default), `Continuous Sweep` (Future).
*   **Status**: Logic for "Continuous" will be a placeholder (implemented as `pass` or simple log), but the functionality is wire-framed into the GUI for easy implementation later.

### C. File Management & Persistence
*   **Settings Persistence**:
    *   On exit, save `last_working_directory` to `settings.toml`.
    *   On startup, load this path.
*   **GUI Controls**:
    *   **Directory Selector**: Button to choose save folder + Text field showing current path.
    *   **File Prefix**: Text input (e.g., "Experiment_A") to auto-name files (e.g., `Experiment_A_001.csv`).

### D. High-Performance Plotting
*   **Live View**: `pyqtgraph` Ring Buffer implementation.
*   **Sweep View**: Static plots for high-precision analysis.

### E. "Safe Save" Workflow
*   **Auto-Save**: Automatic CSV dump to `data/autosaves` before any user interaction.
*   **Recovery**: File exists in `data/autosaves` even if app crashes.

### F. Dynamic Connections (LAN & GPIB)
*   Drivers accept a `connection_config` dict.
*   Logic handles `TCPIP` vs `GPIB` resource string generation automatically.

## 4. Migration Plan

1.  **Init**: Setup project.
2.  **Core**: Define `InstrumentDriver` ABC.
3.  **Mocks**: Implement `MockLaser` and `MockScope` FIRST. This allows developing the GUI without sitting next to the equipment.
4.  **Drivers**: Implement real `Laser` (Santec) and `Scope` (Pico) drivers.
5.  **GUI**: Build `Main Window` with:
    *   Scan Mode Toggle.
    *   File Path Controls.
    *   Live/Sweep Tabs.
6.  **Integration**: Connect GUI -> Engine -> Drivers.
7.  **Final Polish**: Verify settings persistence (Last Dir).

