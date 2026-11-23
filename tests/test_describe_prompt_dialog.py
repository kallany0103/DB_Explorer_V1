"""
tests/test_describe_prompt_dialog.py
Unit tests for DescribePromptDialog.
"""

from PySide6.QtWidgets import QApplication
from dialogs.tools.describe_prompt_dialog import DescribePromptDialog


def test_describe_prompt_dialog_defaults():
    _ = QApplication.instance() or QApplication([])
    dlg = DescribePromptDialog()
    assert dlg.windowTitle() == "Describe (F4)"
    assert dlg.target_name() == ""
    assert not dlg._ok_btn.isEnabled()


def test_describe_prompt_dialog_with_initial_text():
    _ = QApplication.instance() or QApplication([])
    dlg = DescribePromptDialog(initial_text="employees")
    assert dlg.target_name() == "employees"
    assert dlg._ok_btn.isEnabled()


def test_describe_prompt_dialog_text_change_enables_button():
    _ = QApplication.instance() or QApplication([])
    dlg = DescribePromptDialog()
    assert not dlg._ok_btn.isEnabled()

    dlg._input.setText("  public.departments  ")
    assert dlg._ok_btn.isEnabled()
    assert dlg.target_name() == "public.departments"

    dlg._input.setText("   ")
    assert not dlg._ok_btn.isEnabled()
    assert dlg.target_name() == ""
