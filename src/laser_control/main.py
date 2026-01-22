import sys
from PySide6.QtWidgets import QApplication
from .gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Laser Control")

    # Optional: Apply specific stylesheet or PySide6-Material theme here

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
