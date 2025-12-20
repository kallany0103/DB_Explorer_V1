# from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout,
#                              QComboBox, QCheckBox, QDialogButtonBox, QFileDialog, QStyle)
# from PyQt6.QtGui import QIcon
# from PyQt6.QtCore import Qt
# import os  # for file path manipulations


# class ExportDialog(QDialog):
#     def __init__(self, parent=None, default_filename="export.csv"):
#         super().__init__(parent)
#         self.setWindowTitle("Export Data")
#         # Set default initial size (optional)
#         self.resize(500, 300)
        
#         # make dialog resizable
#         self.setSizeGripEnabled(True)
#         self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        
#         #self.setMinimumWidth(550)
#         main_layout = QVBoxLayout(self)
#         tab_widget = QTabWidget()
#         main_layout.addWidget(tab_widget)
#         general_tab = QWidget()
#         options_tab = QWidget()
#         tab_widget.addTab(general_tab, "General")
#         tab_widget.addTab(options_tab, "Options")
#         general_layout = QFormLayout(general_tab)
#         general_layout.addRow("Action:", QLabel("Export"))

#         self.filename_edit = QLineEdit(default_filename)
#         browse_btn = QPushButton()
#         browse_btn.setIcon(self.style().standardIcon(
#             QStyle.StandardPixmap.SP_DirOpenIcon))
#         browse_btn.setFixedSize(30, 25)
#         browse_btn.clicked.connect(self.browse_file)
#         filename_layout = QHBoxLayout()
#         filename_layout.addWidget(self.filename_edit)
#         filename_layout.addWidget(browse_btn)
#         general_layout.addRow("Filename:", filename_layout)
#         self.format_combo = QComboBox()
#         self.format_combo.addItems(["csv", "xlsx"])
#         self.format_combo.setCurrentText("csv")
#         self.format_combo.currentTextChanged.connect(self.on_format_change)
#         general_layout.addRow("Format:", self.format_combo)
#         self.encoding_combo = QComboBox()
#         self.encoding_combo.addItems(['UTF-8', 'LATIN1', 'windows-1252'])
#         self.encoding_combo.setEditable(True)
#         general_layout.addRow("Encoding:", self.encoding_combo)
#         options_layout = QFormLayout(options_tab)
#         self.options_layout = options_layout
#         self.header_check = QCheckBox("Header")
#         self.header_check.setChecked(True)
#         options_layout.addRow("Options:", self.header_check)
#         self.delimiter_label = QLabel("Delimiter:")
#         self.delimiter_combo = QComboBox()
#         self.delimiter_combo.addItems([',', ';', '|', '\\t'])
#         self.delimiter_combo.setEditable(True)
#         self.quote_label = QLabel("Quote character:")
#         self.quote_edit = QLineEdit('"')
#         self.quote_edit.setMaxLength(1)
#         options_layout.addRow(self.delimiter_label, self.delimiter_combo)
#         options_layout.addRow(self.quote_label, self.quote_edit)
#         button_box = QDialogButtonBox(
#             QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
#         button_box.accepted.connect(self.accept)
#         button_box.rejected.connect(self.reject)
#         main_layout.addWidget(button_box)
#         self.on_format_change(self.format_combo.currentText())

#     def on_format_change(self, format_text):
#         is_csv = (format_text == 'csv')
#         self.encoding_combo.setEnabled(is_csv)
#         self.delimiter_label.setVisible(is_csv)
#         self.delimiter_combo.setVisible(is_csv)
#         self.quote_label.setVisible(is_csv)
#         self.quote_edit.setVisible(is_csv)
#         current_filename = self.filename_edit.text()
#         base_name, _ = os.path.splitext(current_filename)
#         self.filename_edit.setText(f"{base_name}.{format_text}")

#     def browse_file(self):
#         file_filter = "CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"
#         path, _ = QFileDialog.getSaveFileName(
#             self, "Select Output File", self.filename_edit.text(), file_filter)
#         if path:
#             self.filename_edit.setText(path)

    
#     def get_options(self):
#         delimiter = self.delimiter_combo.currentText()
#         if delimiter == '\\t':
#           delimiter = '\t'
#         return {
#            "filename": self.filename_edit.text(),
#            "format": self.format_combo.currentText(),   # <<< ADD THIS
#            "encoding": self.encoding_combo.currentText(),
#            "header": self.header_check.isChecked(),
#            "delimiter": delimiter,
#            "quote": self.quote_edit.text()
#        }

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
                             QLabel, QLineEdit, QPushButton, QHBoxLayout,
                             QComboBox, QCheckBox, QDialogButtonBox, QFileDialog, QStyle)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
import os 

class ExportDialog(QDialog):
    def __init__(self, parent=None, default_filename="export.csv"):
        super().__init__(parent)
        self.setWindowTitle("Export Data")
        self.resize(550, 350)
        
        self.setSizeGripEnabled(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        
        main_layout = QVBoxLayout(self)
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        general_tab = QWidget()
        options_tab = QWidget()
        
        tab_widget.addTab(general_tab, "General")
        tab_widget.addTab(options_tab, "Options")
        
        # --- General Tab Layout ---
        general_layout = QFormLayout(general_tab)
        
        # 1. Action Label
        general_layout.addRow("Action:", QLabel("Export Data"))
        
        # 2. File Name Input (Only Name)
        # এখানে শুধুই ফাইলের নাম থাকবে
        self.filename_edit = QLineEdit(default_filename)
        general_layout.addRow("File Name:", self.filename_edit)

        # 3. Location Input (Default: Desktop)
        # ডেস্কটপ পাথ বের করা হচ্ছে
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        
        self.location_edit = QLineEdit(desktop_path)
        
        browse_btn = QPushButton()
        browse_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        browse_btn.setFixedSize(30, 25)
        browse_btn.setToolTip("Browse Folder")
        browse_btn.clicked.connect(self.browse_folder) # ফোল্ডার ব্রাউজ ফাংশন
        
        location_layout = QHBoxLayout()
        location_layout.addWidget(self.location_edit)
        location_layout.addWidget(browse_btn)
        
        # আলাদা লেবেলে লোকেশন দেখানো হচ্ছে
        general_layout.addRow("Location:", location_layout)

        # 4. Format Selection
        self.format_combo = QComboBox()
        self.format_combo.addItems(["csv", "xlsx", "txt"])
        self.format_combo.setCurrentText("csv")
        self.format_combo.currentTextChanged.connect(self.on_format_change)
        general_layout.addRow("Format:", self.format_combo)

        # 5. Encoding
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(['UTF-8', 'LATIN1', 'windows-1252', 'utf-8-sig'])
        self.encoding_combo.setEditable(True)
        general_layout.addRow("Encoding:", self.encoding_combo)
        
        # --- Options Tab Layout ---
        options_layout = QFormLayout(options_tab)
        self.options_layout = options_layout
        
        self.header_check = QCheckBox("Include Headers")
        self.header_check.setChecked(True)
        options_layout.addRow("Headers:", self.header_check)
        
        self.delimiter_label = QLabel("Delimiter:")
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems([',', ';', '|', '\\t'])
        self.delimiter_combo.setEditable(True)
        
        self.quote_label = QLabel("Quote character:")
        self.quote_edit = QLineEdit('"')
        self.quote_edit.setMaxLength(1)
        
        options_layout.addRow(self.delimiter_label, self.delimiter_combo)
        options_layout.addRow(self.quote_label, self.quote_edit)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        # Initial State trigger
        self.on_format_change(self.format_combo.currentText())

    def on_format_change(self, format_text):
        """ফরম্যাট বদলালে এক্সটেনশন এবং অপশন আপডেট করবে"""
        is_csv = (format_text in ['csv', 'txt'])
        
        self.encoding_combo.setEnabled(is_csv)
        self.delimiter_label.setVisible(is_csv)
        self.delimiter_combo.setVisible(is_csv)
        self.quote_label.setVisible(is_csv)
        self.quote_edit.setVisible(is_csv)
        
        # ফাইলের নামের এক্সটেনশন আপডেট করা (লোকেশন ঠিক রেখে)
        current_filename = self.filename_edit.text()
        base_name, _ = os.path.splitext(current_filename)
        
        # ডট (.) হ্যান্ডেল করা
        if format_text.startswith("."):
             self.filename_edit.setText(f"{base_name}{format_text}")
        else:
             self.filename_edit.setText(f"{base_name}.{format_text}")

    def browse_folder(self):
        """ফোল্ডার সিলেক্ট করার জন্য"""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.location_edit.text()
        )
        if folder:
            self.location_edit.setText(folder)

    def get_options(self):
        """ফাইনাল অপশন রিটার্ন করবে"""
        delimiter = self.delimiter_combo.currentText()
        if delimiter == '\\t':
          delimiter = '\t'
        
        # নাম এবং পাথ জোড়া লাগানো হচ্ছে (Joining Path + Filename)
        # যাতে main_window.py তে কোনো চেঞ্জ করতে না হয়
        full_path = os.path.join(self.location_edit.text(), self.filename_edit.text())

        return {
           "filename": full_path, # এখানে ফুল পাথ যাচ্ছে
           "format": self.format_combo.currentText(),
           "encoding": self.encoding_combo.currentText(),
           "header": self.header_check.isChecked(),
           "delimiter": delimiter,
           "quote": self.quote_edit.text()
       }