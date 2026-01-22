from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
import pyqtgraph as pg
import numpy as np
from lmfit.models import LorentzianModel, ConstantModel


class SweepPlotWidget(QWidget):
    """
    Widget for viewing acquired spectra and analyzing peaks.
    """

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.current_wavelengths = None
        self.current_signal = None

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Info Label
        self.lbl_info = QLabel("No Data. Run a sweep to begin.")
        layout.addWidget(self.lbl_info)

        # Plot
        self.plot_widget = pg.PlotWidget()
        self.plot = self.plot_widget.getPlotItem()
        self.plot.setLabel("bottom", "Wavelength", "nm")
        self.plot.setLabel("left", "Amplitude", "V")

        self.curve_data = self.plot.plot(pen="w", name="Data")
        self.curve_fit = self.plot.plot(pen="r", width=2, name="Fit")

        # ROI for selection
        self.roi = pg.LinearRegionItem()
        self.roi.setZValue(10)
        self.roi.sigRegionChanged.connect(self.update_fit)
        self.plot.addItem(self.roi)
        self.roi.hide()  # Hide until data exists

        layout.addWidget(self.plot_widget)

    def set_data(self, wavelengths, signal):
        self.current_wavelengths = wavelengths
        self.current_signal = signal

        self.curve_data.setData(wavelengths, signal)
        self.curve_fit.setData([], [])  # Clear fit
        self.lbl_info.setText("Data Loaded. Drag region to fit.")

        # Auto-set ROI to center 50%
        mid = len(wavelengths) // 2
        span = len(wavelengths) // 4

        # Handle empty
        if len(wavelengths) > 1:
            self.roi.setRegion((wavelengths[mid - span], wavelengths[mid + span]))
            self.roi.show()
            self.update_fit()

    def update_fit(self):
        if self.current_wavelengths is None:
            return

        min_x, max_x = self.roi.getRegion()

        # Filter data
        mask = (self.current_wavelengths >= min_x) & (self.current_wavelengths <= max_x)
        x_sub = self.current_wavelengths[mask]
        y_sub = self.current_signal[mask]

        if len(x_sub) < 10:
            return  # Too few points

        try:
            # Fitting Logic (Lorentzian)
            model = LorentzianModel() + ConstantModel()

            # Guesses
            amp_guess = np.max(y_sub) - np.min(y_sub)
            center_guess = x_sub[
                np.argmax(np.abs(y_sub - np.mean(y_sub)))
            ]  # Peak or Dip
            c_guess = np.mean(y_sub)

            params = model.make_params(
                amplitude=amp_guess, center=center_guess, sigma=0.01, c=c_guess
            )

            result = model.fit(y_sub, params, x=x_sub)

            # Plot Fit
            fit_x = np.linspace(min_x, max_x, 500)
            fit_y = result.eval(x=fit_x)
            self.curve_fit.setData(fit_x, fit_y)

            # Calculate Q
            center = result.params["center"].value
            fwhm = result.params["fwhm"].value
            q_factor = center / fwhm if fwhm != 0 else 0

            self.lbl_info.setText(
                f"Fit Results: Center={center:.4f}nm, Q={q_factor:.2e}"
            )

        except Exception as e:
            self.lbl_info.setText(f"Fit Failed: {str(e)}")
