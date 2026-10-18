import time
from typing import Any, Type
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QRect
from ui.components import PrimaryButton, SecondaryButton, ToastNotification
from workers.workers import WorkerThread
import db
from db.db_retrieval import get_groups_by_type


class FitScrollArea(QScrollArea):
    """A scroll area that constrains its child widget width to the exact viewport width."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.widget():
            target_w = max(100, self.viewport().width())
            self.widget().setFixedWidth(target_w)


class BaseConnectionDialog(QDialog):
    """
    Base class for all connection dialogs. Can host a modern EngineForm standalone
    or render legacy inputs with standard window layout, centering, and screen safety.
    """
    def __init__(
        self,
        parent=None,
        conn_data=None,
        is_editing=False,
        type_id=None,
        group_id=None,
        title="Connection",
        subtitle="",
        fixed_size=None,
        min_size=None,
        form_cls: Type[Any] | None = None,
    ):
        top_window = parent.window() if parent else None
        super().__init__(top_window or parent)

        self.manager = parent
        self._was_updated = False
        self.conn_data = conn_data
        self.type_id = type_id
        self.group_id = group_id
        self.form_cls = form_cls
        self._min_size_requested = min_size
        self._fixed_size_requested = fixed_size

        self.is_editing = is_editing or (conn_data is not None)
        self.original_password = str(conn_data.get("password", "") or "") if (conn_data and conn_data.get("password") is not None) else None
        self._showing_pwd_warning = False
        self._pwd_editing_connected = False

        clean_title = title if "Connection" in title else f"{title} Connection"
        self.setWindowTitle(f"Edit {clean_title}" if self.is_editing else f"New {clean_title}")
        self.setObjectName("standaloneConnDialog")

        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 16)
        self.main_layout.setSpacing(12)

        # 1. Header (used for legacy dialogs; modern EngineForms provide their own header)
        self.header_title = QLabel(f"{title} Connection" if "Connection" not in title else title)
        self.header_title.setObjectName("dialogTitle")
        self.header_subtitle = QLabel(subtitle)
        self.header_subtitle.setObjectName("dialogSubtitle")

        # 2. Scroll Area
        self.scroll_area = FitScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setObjectName("dialogScrollArea")

        if self.form_cls:
            self.engine_form = self.form_cls(
                type_id=self.type_id,
                group_id=self.group_id,
                parent=self,
            )
            self.engine_form.set_type_context(self.type_id, self.group_id)
            if self.conn_data:
                self.engine_form.load_data(self.conn_data)
            self.scroll_area.setWidget(self.engine_form)
            self.main_layout.addWidget(self.scroll_area, 1)
        else:
            self.main_layout.addWidget(self.header_title)
            self.main_layout.addWidget(self.header_subtitle)
            self.form_widget = QWidget()
            self.form_widget.setObjectName("dialogFormWidget")
            self.form = QFormLayout(self.form_widget)
            self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
            self.form.setHorizontalSpacing(18)
            self.form.setVerticalSpacing(10)
            self.form.setContentsMargins(0, 4, 12, 4)

            self.group_combo = QComboBox()
            self.new_group_btn = SecondaryButton("New Group")
            self.new_group_btn.setFixedWidth(110)
            self.new_group_btn.clicked.connect(self._create_new_group)
            
            self.group_layout = QHBoxLayout()
            self.group_layout.setSpacing(10)
            self.group_layout.setContentsMargins(0, 0, 0, 0)
            self.group_layout.addWidget(self.group_combo)
            self.group_layout.addWidget(self.new_group_btn)

            if self.type_id:
                self._populate_groups()
                
            if self.group_id:
                index = self.group_combo.findData(self.group_id)
                if index >= 0:
                    self.group_combo.setCurrentIndex(index)

            self.group_row_widget = QWidget()
            self.group_row_widget.setMinimumHeight(36)
            self.group_row_layout = QHBoxLayout(self.group_row_widget)
            self.group_row_layout.setContentsMargins(0, 2, 0, 2)
            self.group_row_layout.addLayout(self.group_layout)
            
            self.form.addRow("Group:", self.group_row_widget)
            
            should_show_group = self.is_editing or not self.group_id
            if not should_show_group:
                self.group_row_widget.hide()
                label = self.form.labelForField(self.group_row_widget)
                if label:
                    label.hide()

            self.setup_inputs()
            self.scroll_area.setWidget(self.form_widget)
            self.main_layout.addWidget(self.scroll_area, 1)

        if self.original_password is not None:
            self.set_original_password(self.original_password)

        # 3. Action Buttons
        self.test_btn = SecondaryButton("Test Connection")
        self.test_btn.clicked.connect(self.testConnection)

        self.cancel_btn = SecondaryButton("Cancel")
        self.cancel_btn.setFixedWidth(84)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = PrimaryButton("Update" if self.is_editing else "Save")
        self.save_btn.setFixedWidth(84)
        self.save_btn.clicked.connect(self.saveConnection)

        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.test_btn)
        self.button_layout.addWidget(self.cancel_btn)
        self.button_layout.addWidget(self.save_btn)

        self.main_layout.addLayout(self.button_layout)

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_inside_parent_and_screen()

    def _ensure_inside_parent_and_screen(self):
        # 1. Determine screen available geometry
        top_win = self.parentWidget().window() if self.parentWidget() else None
        screen = None
        if top_win and top_win.screen():
            screen = top_win.screen()
        elif self.screen():
            screen = self.screen()
        else:
            screen = QApplication.primaryScreen()

        screen_rect = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        # 2. Determine target boundary (parent application window if valid, else screen)
        if (
            top_win
            and top_win.isVisible()
            and not top_win.isMinimized()
            and top_win.width() > 300
            and top_win.height() > 300
        ):
            target_rect = top_win.geometry()
        else:
            target_rect = screen_rect

        # 3. Calculate max allowed dimensions to never exceed parent or screen (cap width at 700px, height at 680px)
        MAX_DIALOG_WIDTH = 700
        MAX_DIALOG_HEIGHT = 680
        max_allowed_w = max(360, min(MAX_DIALOG_WIDTH, target_rect.width() - 24, screen_rect.width() - 24))
        max_allowed_h = max(300, min(MAX_DIALOG_HEIGHT, target_rect.height() - 36, screen_rect.height() - 36))

        # 4. Handle fixed or min size requests within safe bounds
        if self._fixed_size_requested:
            fw = min(self._fixed_size_requested[0], max_allowed_w)
            fh = min(self._fixed_size_requested[1], max_allowed_h)
            self.setFixedSize(fw, fh)
        else:
            min_w = 480
            min_h = 320
            if self._min_size_requested:
                min_w = min(self._min_size_requested[0], max_allowed_w)
                min_h = min(self._min_size_requested[1], max_allowed_h)
            self.setMinimumSize(min_w, min_h)
            self.setMaximumSize(max_allowed_w, max_allowed_h)

            # Compute ideal content height
            if self.form_cls and hasattr(self, "engine_form"):
                form_h = self.engine_form.sizeHint().height()
                content_h = form_h + self.button_layout.sizeHint().height() + 60
            else:
                header_h = (
                    self.header_title.sizeHint().height()
                    + self.header_subtitle.sizeHint().height()
                )
                form_h = self.form_widget.sizeHint().height() if hasattr(self, "form_widget") else 300
                content_h = header_h + form_h + self.button_layout.sizeHint().height() + 50
            ideal_w = min(max(self.width(), 640), max_allowed_w)
            ideal_h = min(max(content_h, min_h), max_allowed_h)
            self.resize(ideal_w, ideal_h)

        # 5. Calculate centered position relative to target_rect
        center_x = target_rect.x() + (target_rect.width() - self.width()) // 2
        center_y = target_rect.y() + (target_rect.height() - self.height()) // 2

        # 6. Strictly clamp within BOTH target_rect and screen_rect
        clamp_left = max(screen_rect.left() + 8, target_rect.left() + 8)
        clamp_right = min(screen_rect.right() - self.width() - 8, target_rect.right() - self.width() - 8)
        clamp_top = max(screen_rect.top() + 8, target_rect.top() + 8)
        clamp_bottom = min(screen_rect.bottom() - self.height() - 8, target_rect.bottom() - self.height() - 8)

        if clamp_right < clamp_left:
            final_x = clamp_left
        else:
            final_x = max(clamp_left, min(center_x, clamp_right))

        if clamp_bottom < clamp_top:
            final_y = clamp_top
        else:
            final_y = max(clamp_top, min(center_y, clamp_bottom))

        self.move(final_x, final_y)

    def _populate_groups(self):
        self.group_combo.clear()
        groups = get_groups_by_type(self.type_id)
        for g in groups:
            self.group_combo.addItem(g["name"], g["id"])
            
    def _create_new_group(self):
        name, ok = QInputDialog.getText(self, "New Group", "Enter group name:")
        if ok and name.strip():
            try:
                db.add_connection_group(name.strip(), self.type_id)
                self._populate_groups()
                index = self.group_combo.findText(name.strip())
                if index >= 0:
                    self.group_combo.setCurrentIndex(index)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create group:\n{e}")

    # Subclass hooks
    def setup_inputs(self):
        pass

    def set_original_password(self, pwd):
        self.original_password = str(pwd or "")
        if hasattr(self, 'password_input') and not self._pwd_editing_connected:
            self.password_input.editingFinished.connect(self._on_password_editing_finished)
            self._pwd_editing_connected = True

    def _on_password_editing_finished(self):
        if self._showing_pwd_warning:
            return
        if self.is_editing and self.original_password is not None and hasattr(self, 'password_input'):
            if self.password_input.text() != self.original_password:
                self._showing_pwd_warning = True
                QMessageBox.warning(
                    self,
                    "Reset Password",
                    "Password cannot be changed directly from Edit Connection.\n"
                    "Please use 'Change Password' to reset or change your password."
                )
                self.password_input.setText(self.original_password)
                self._showing_pwd_warning = False

    def check_password_modification(self):
        if self._showing_pwd_warning:
            return False
        if self.is_editing and self.original_password is not None and hasattr(self, 'password_input'):
            if self.password_input.text() != self.original_password:
                self._showing_pwd_warning = True
                QMessageBox.warning(
                    self,
                    "Reset Password",
                    "Password cannot be changed directly from Edit Connection.\n"
                    "Please use 'Change Password' to reset or change your password."
                )
                self.password_input.setText(self.original_password)
                self._showing_pwd_warning = False
                return False
        return True

    def testConnection(self):
        if not self.check_password_modification():
            return
        if hasattr(self, "engine_form") and hasattr(self.engine_form, "test_connection"):
            self.test_btn.start_loading("Testing")
            self._test_worker = WorkerThread(self.engine_form.test_connection)
            self._test_worker.finished_signal.connect(self._on_engine_test_finished)
            self._test_worker.start()
        else:
            self.test_connection_impl()

    def _on_engine_test_finished(self, result: Any, error: Exception | str | None) -> None:
        self.test_btn.stop_loading()
        if error:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect:\n{error}")
            return
        success, msg = result if isinstance(result, tuple) else (False, str(result))
        if success:
            QMessageBox.information(self, "Connection Test", msg or "Connection successful!")
        else:
            QMessageBox.critical(self, "Connection Test Failed", msg or "Failed to connect.")

    def saveConnection(self):
        if hasattr(self, "group_combo") and self.group_combo.currentIndex() == -1:
            QMessageBox.warning(self, "Missing Info", "Please select or create a group.")
            return
        if not self.check_password_modification():
            return
        if hasattr(self, "engine_form") and hasattr(self.engine_form, "validate_inputs"):
            valid, msg = self.engine_form.validate_inputs()
            if not valid:
                QMessageBox.warning(self, "Validation", msg)
                return

        if self.is_editing:
            self._do_in_place_update()
        else:
            self.save_connection_impl()
            self.accept()

    def _do_in_place_update(self):
        new_data = self.getData()
        if not new_data.get("id") and self.conn_data and "id" in self.conn_data:
            new_data["id"] = self.conn_data["id"]

        orig_pwd = str(self.original_password or "")
        if str(new_data.get("password", "") or "") != orig_pwd:
            QMessageBox.warning(
                self,
                "Reset Password",
                "Password cannot be changed directly from Edit Connection.\n"
                "Please use 'Change Password' to reset or change your password."
            )
            return
        new_data["password"] = orig_pwd

        self.save_btn.start_loading("Updating")

        def _worker_update():
            t0 = time.time()
            db.update_connection(new_data)
            code = str(new_data.get("code") or new_data.get("db_type") or "").upper()
            if "ORACLE" in code:
                db.invalidate_oracle_pool(new_data)
            elif "POSTGRES" in code:
                db.invalidate_pool(new_data)
            elapsed = time.time() - t0
            if elapsed < 0.4:
                time.sleep(0.4 - elapsed)
            return new_data

        self._update_worker = WorkerThread(_worker_update)
        self._update_worker.finished_signal.connect(self._on_in_place_update_finished)
        self._update_worker.start()

    def _on_in_place_update_finished(self, result: Any, error: Exception | str | None) -> None:
        self.save_btn.stop_loading()
        if error:
            QMessageBox.critical(self, "Update Error", f"Failed to update connection:\n{error}")
            return

        self._was_updated = True
        conn_name = result.get("name", "Connection")
        if self.conn_data:
            self.conn_data.update(result)

        if hasattr(self, "cancel_btn"):
            self.cancel_btn.setText("Close")

        # Refresh manager tree in the background on the Qt main thread
        mgr = getattr(self, "manager", None)
        if not mgr and self.parent():
            mgr = self.parent()
        if mgr and hasattr(mgr, "load_data"):
            try:
                if hasattr(mgr, "active_postgres_conn") and mgr.active_postgres_conn and mgr.active_postgres_conn.get("id") == result.get("id"):
                    mgr.active_postgres_conn = result
                if hasattr(mgr, "_save_tree_expansion_state"):
                    mgr._save_tree_expansion_state()
                mgr.load_data()
                if hasattr(mgr, "_restore_tree_expansion_state"):
                    mgr._restore_tree_expansion_state()
                if hasattr(mgr, "refresh_all_comboboxes"):
                    mgr.refresh_all_comboboxes()
            except Exception:
                pass

        ToastNotification.show_toast(self, f"'{conn_name}' updated successfully!", kind="success")

    def populate_from_conn_data(self, conn_data: dict[str, Any]) -> None:
        self.conn_data = conn_data
        if hasattr(self, "engine_form"):
            self.engine_form.load_data(conn_data)

    def __getattr__(self, name: str) -> Any:
        if "engine_form" in self.__dict__:
            engine_form = self.__dict__["engine_form"]
            if hasattr(engine_form, name):
                return getattr(engine_form, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def getData(self) -> dict[str, Any]:
        if self.form_cls and hasattr(self, "engine_form"):
            data = self.engine_form.get_data()
            if self.conn_data and "id" in self.conn_data and "id" not in data:
                data["id"] = self.conn_data["id"]
            return data
        return {}

    def test_connection_impl(self):
        pass

    def save_connection_impl(self):
        pass
