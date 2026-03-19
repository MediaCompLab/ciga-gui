import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

# Add CIGA root to sys.path so ciga imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
ciga_gui_root = os.path.dirname(current_dir)
ciga_root = os.path.dirname(ciga_gui_root)
if ciga_root not in sys.path:
    sys.path.append(ciga_root)

from src.ui.main_window import MainWindow

def get_resource_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ciga_gui_root = os.path.dirname(current_dir)
        ciga_root = os.path.dirname(ciga_gui_root)
        return os.path.join(ciga_root, filename)

def main():
    app = QApplication(sys.argv)

    # Set Logo based on dark/light mode
    is_dark = app.palette().window().color().lightness() < 128
    logo_filename = "logo_white.png" if is_dark else "logo_black.png"
    logo_path = get_resource_path(logo_filename)
    
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
