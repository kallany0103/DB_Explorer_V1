"""
tests/test_quick_describe_dialog.py
Unit tests for QuickDescribeDialog.
"""

from PySide6.QtWidgets import QApplication
from dialogs.tools.quick_describe_dialog import QuickDescribeDialog, _extract_object_name


def test_extract_object_name():
    assert _extract_object_name("SELECT * FROM employees WHERE id = 1") == "employees"
    assert _extract_object_name('SELECT * FROM "hr"."departments"') == "hr.departments"
    assert _extract_object_name("employees") == "employees"


def test_quick_describe_dialog_defaults():
    _ = QApplication.instance() or QApplication([])
    dlg = QuickDescribeDialog()
    assert dlg.windowTitle() == "Quick Describe"
    assert not dlg.describe_btn.isEnabled()
    assert not dlg.desc_close_btn.isEnabled()


def test_quick_describe_dialog_text_validation():
    _ = QApplication.instance() or QApplication([])
    dlg = QuickDescribeDialog()
    assert not dlg.describe_btn.isEnabled()

    dlg.name_edit.setText("employees")
    assert dlg.describe_btn.isEnabled()
    assert dlg.desc_close_btn.isEnabled()

    dlg.name_edit.setText("")
    assert not dlg.describe_btn.isEnabled()
    assert not dlg.desc_close_btn.isEnabled()


def test_quick_describe_resolve_target():
    _ = QApplication.instance() or QApplication([])
    dlg = QuickDescribeDialog()
    dlg.name_edit.setText("employees")
    assert dlg._resolve_target() == "employees"

    # Select specific schema
    dlg.owner_combo.addItem("hr")
    dlg.owner_combo.setCurrentText("hr")
    assert dlg._resolve_target() == '"hr"."employees"'

    # Reset schema and check case sensitivity
    dlg.owner_combo.setCurrentIndex(0)
    dlg.case_chk.setChecked(True)
    assert dlg._resolve_target() == '"employees"'
