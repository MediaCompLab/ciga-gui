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

def main():
    app = QApplication(sys.argv)
    
    # Set Logo based on dark/light mode
    is_dark = app.palette().window().color().lightness() < 128
    logo_path = os.path.join(ciga_root, "logo_white.png" if is_dark else "logo_black.png")
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
