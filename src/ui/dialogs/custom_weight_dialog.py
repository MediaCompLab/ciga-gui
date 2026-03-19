from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QPlainTextEdit, QPushButton, QFileDialog)

class CustomWeightDialog(QDialog):
    def __init__(self, parent=None, columns=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Weight Function")
        self.resize(500, 450)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select Interaction Column:"))
        self.cb_inter_col = QComboBox()
        self.cb_inter_col.addItems(columns or [])
        layout.addWidget(self.cb_inter_col)
        
        layout.addWidget(QLabel("Define Python function `custom_weight(interaction)`:"))
        
        self.code_editor = QPlainTextEdit()
        # Default snippet
        default_code = (
            "def custom_weight(interaction):\n"
            "    # Example: return the length of the string text\n"
            "    if not isinstance(interaction, str):\n"
            "        return 1.0\n"
            "    return float(len(interaction))\n"
        )
        self.code_editor.setPlainText(default_code)
        
        # Use a fixed-width font
        font = self.code_editor.font()
        font.setFamily("Courier New")
        self.code_editor.setFont(font)
        
        layout.addWidget(self.code_editor)
        
        btn_layout = QHBoxLayout()
        self.btn_load_script = QPushButton("Load from .py File...")
        self.btn_apply = QPushButton("Apply to Data")
        
        btn_layout.addWidget(self.btn_load_script)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        
        layout.addLayout(btn_layout)
        
        self.btn_load_script.clicked.connect(self.load_script)
        self.btn_apply.clicked.connect(self.accept)
        
    def load_script(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Python Script", "",
            "Python Files (*.py)"
        )
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.code_editor.setPlainText(f.read())
                
    def get_function_and_column(self):
        code = self.code_editor.toPlainText()
        col = self.cb_inter_col.currentText()
        return code, col
