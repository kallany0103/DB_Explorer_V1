from PyQt6.QtWidgets import QLabel, QPushButton, QStackedWidget, QWidget


def show_loading_view(tab):
    if not tab:
        return

    results_stack = tab.findChild(QStackedWidget, "results_stacked_widget")
    if not results_stack:
        return

    results_stack.setCurrentIndex(4)
    spinner_label = results_stack.findChild(QLabel, "spinner_label")
    if spinner_label and spinner_label.movie():
        spinner_label.movie().start()
        spinner_label.show()


def show_error_view(tab):
    if not tab:
        return

    results_stack = tab.findChild(QStackedWidget, "results_stacked_widget")
    if results_stack:
        results_stack.setCurrentIndex(1)

    header = tab.findChild(QWidget, "resultsHeader")
    if header:
        buttons = header.findChildren(QPushButton)
        if len(buttons) >= 2:
            buttons[0].setChecked(False)
            buttons[1].setChecked(True)

    results_info_bar = tab.findChild(QWidget, "resultsInfoBar")
    if results_info_bar:
        results_info_bar.hide()
