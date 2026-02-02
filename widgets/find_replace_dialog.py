
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QCheckBox, QWidget, 
                             QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal

class FindReplaceDialog(QDialog):
    find_next = pyqtSignal(str, bool, bool) # text, case_sensitive, whole_word
    find_previous = pyqtSignal(str, bool, bool)
    replace = pyqtSignal(str, str, bool, bool) # target, replacement, case, whole
    replace_all = pyqtSignal(str, str, bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find and Replace")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint) # Modeless behavior often needs this or just use .show()
        self.setModal(False) 
        self.resize(350, 180)

        layout = QVBoxLayout(self)
        
        # Grid for Inputs
        grid_layout = QGridLayout()
        
        # Find
        self.find_label = QLabel("Find:")
        self.find_input = QLineEdit()
        grid_layout.addWidget(self.find_label, 0, 0)
        grid_layout.addWidget(self.find_input, 0, 1)

        # Replace
        self.replace_label = QLabel("Replace with:")
        self.replace_input = QLineEdit()
        grid_layout.addWidget(self.replace_label, 1, 0)
        grid_layout.addWidget(self.replace_input, 1, 1)
        
        layout.addLayout(grid_layout)

        # Options
        options_layout = QHBoxLayout()
        self.case_check = QCheckBox("Case Sensitive")
        self.whole_word_check = QCheckBox("Whole Word")
        options_layout.addWidget(self.case_check)
        options_layout.addWidget(self.whole_word_check)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Buttons
        btn_layout = QGridLayout()
        
        self.btn_find_next = QPushButton("Find Next")
        self.btn_find_prev = QPushButton("Find Previous")
        self.btn_replace = QPushButton("Replace")
        self.btn_replace_all = QPushButton("Replace All")
        
        btn_layout.addWidget(self.btn_find_next, 0, 0)
        btn_layout.addWidget(self.btn_find_prev, 0, 1)
        btn_layout.addWidget(self.btn_replace, 1, 0)
        btn_layout.addWidget(self.btn_replace_all, 1, 1)

        layout.addLayout(btn_layout)

        # Connections
        self.btn_find_next.clicked.connect(self.on_find_next)
        self.btn_find_prev.clicked.connect(self.on_find_prev)
        self.btn_replace.clicked.connect(self.on_replace)
        self.btn_replace_all.clicked.connect(self.on_replace_all)

    def on_find_next(self):
        text = self.find_input.text()
        if text:
            self.find_next.emit(text, self.case_check.isChecked(), self.whole_word_check.isChecked())

    def on_find_prev(self):
        text = self.find_input.text()
        if text:
            self.find_previous.emit(text, self.case_check.isChecked(), self.whole_word_check.isChecked())

    def on_replace(self):
        target = self.find_input.text()
        replacement = self.replace_input.text()
        if target:
            self.replace.emit(target, replacement, self.case_check.isChecked(), self.whole_word_check.isChecked())

    def on_replace_all(self):
        target = self.find_input.text()
        replacement = self.replace_input.text()
        if target:
            self.replace_all.emit(target, replacement, self.case_check.isChecked(), self.whole_word_check.isChecked())

    def set_find_text(self, text):
        self.find_input.setText(text)
        self.find_input.selectAll()
        self.find_input.setFocus()
