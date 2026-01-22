# Legacy Laser Control Code Analysis & Reproduction Plan

## 1. System Overview
The file `LaserConrtolOLD.py` is a monolithic Python application providing a Graphical User Interface (GUI) for controlling a tunable laser source and an oscilloscope to perform optical spectroscopy. It is built using `PyQt5` for the UI and `matplotlib` for data visualization.

### Hardware Requirements
The code is hardcoded for specific hardware:
*   **Oscilloscope**: PicoScope 5000a Series (using `picoscope.ps5000a` driver).
*   **Laser Source**: A tunable laser controlled via VISA/GPIB (Address: `GPIB0::10::INSTR`). The SCPI command set suggests compatibility with Keysight/Agilent style tunable lasers (e.g., 816x series or similar).

### Software Dependencies
*   `PyQt5` (GUI)
*   `matplotlib` (Plotting)
*   `numpy` (Data processing)
*   `pyvisa` (Laser communication)
*   `picoscope` (Oscilloscope driver)
*   `pandas` (Data export)
*   `lmfit` (Curve fitting)

## 2. Functional Workflows

### A. Initialization
1.  **Startup**: When the application launches, the `InstrumentManager` attempts to connect immediately in the main thread.
2.  **PicoScope Setup**: 
    *   Resolution: 12-bit.
    *   Channel A: DC Coupling, ±5V range, enabled (Trigger Source).
    *   Channel B: DC Coupling, ±2V range, enabled (Signal Input).
3.  **Laser Setup**: Opens VISA resource `GPIB0::10::INSTR`.

### B. Sweep Mode (Primary Function)
Used to acquire a spectrum (Amplitude vs. Wavelength).
1.  **Configuration**: User inputs:
    *   Start/End Wavelength (nm)
    *   Power (dBm)
    *   Sweep Speed (nm/s)
    *   Number of Samples
2.  **Execution** (Background Thread `SweepThread`):
    *   Calculates sweep duration and sampling interval.
    *   Sets PicoScope trigger: Channel A, Rising Edge, 1V threshold.
    *   Configures Laser: Sets wavelength range, power, mode to Continuous Sweep (`:WAV:SWE:MOD 1`), and enables trigger output (`:TRIG:OUTP 2`).
    *   **Trigger Sequence**:
        1.  Laser output enabled.
        2.  Sleep (0.5s).
        3.  Laser sweep start command (`:WAV:SWE 1`).
        4.  PicoScope captures block (`runBlock`).
    *   **Data Processing**:
        *   Maps time-domain data from scope to wavelength domain using the formula: `Wavelength = Start + (Time * Speed)`.
3.  **Visualization**: Plots Channel B data against the calculated Wavelength axis.

### C. Live Power Mode
Used for alignment or continuous monitoring at a fixed wavelength.
1.  **Configuration**:
    *   Sets Laser to Continuous Wave (CW) mode (`:WAV:SWE:MOD 0`).
    *   Sets fixed Wavelength and Power.
    *   Disables Scope Trigger (Free run / Timeout).
2.  **Execution** (Background Thread `LiveDataThread`):
    *   Polls data continuously (1ms interval, 100ms duration chunks).
3.  **Visualization**:
    *   Plots Ch A and Ch B voltage vs. Time.
    *   Displays real-time average and standard deviation (10-sample rolling window).

### D. Data Analysis (Q-Factor)
1.  User selects a region on the main plot using a drag-selector (`SpanSelector`).
2.  **Curve Fitting**:
    *   Model: `LorentzianModel` (Peak) + `ConstantModel` (Offset) + `SplineModel` (Background).
    *   Initial Guesses: Estimated from data (max amplitude, center index).
3.  **Metrics**:
    *   **Q-Factor**: `Center_Wavelength / FWHM`.
    *   **Linewidth (Δf)**: Calculated in Hz.
4.  **Output**: Updates a secondary zoom plot with the raw data and the fitted curve.

### E. Data Export
*   On sweep completion, automatically prompts to save data to CSV (`Wavelength_nm`, `Amplitude_V`).

## 3. Potential Issues & Risks (Current State)
*   **Blocking Startup**: If instruments are off or disconnected, the application UI will likely freeze or crash on launch.
*   **Hardcoded Configuration**: Changing GPIB addresses or Scope channels requires editing code.
*   **Error Masking**: Broad `try/except` blocks print errors to a log window but may leave the hardware in an undefined state.
*   **Resource Management**: If the app crashes, handles to the PicoScope or VISA resource might remain open, requiring a hard reset of the hardware or python kernel.
