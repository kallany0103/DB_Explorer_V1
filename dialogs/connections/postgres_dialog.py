from PySide6.QtWidgets import QLineEdit, QMessageBox
from ui.components import PasswordBox
from .base_connection_dialog import BaseConnectionDialog
import psycopg2
from workers.workers import WorkerThread



class PostgresConnectionDialog(BaseConnectionDialog):
    def __init__(self, parent=None, is_editing=False, type_id=None, group_id=None):
        super().__init__(
            parent=parent, 
            is_editing=is_editing, 
            type_id=type_id, 
            group_id=group_id, 
            title="PostgreSQL", 
            subtitle="Configure connection details and test before saving.",
            min_size=(560, 580)
        )
    def setup_inputs(self):
        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.host_input = QLineEdit()
        self.port_input = QLineEdit()
        self.db_input = QLineEdit()
        self.user_input = QLineEdit()
        self.password_input = PasswordBox()

        self.form.addRow("Connection Name:", self.name_input)
        self.form.addRow("Short Name:", self.short_name_input)
        self.form.addRow("Host:", self.host_input)
        self.form.addRow("Port:", self.port_input)
        self.form.addRow("Database:", self.db_input)
        self.form.addRow("User:", self.user_input)
        self.form.addRow("Password:", self.password_input)
        
        if not (self.is_editing or not self.group_id):
            self.setMinimumHeight(520)


    def _run_connection_test(self, db_name, host, port, user, password, extra):
        try:
            conn = psycopg2.connect(
                host=host,
                port=int(port) if port else 5432,
                database=db_name,
                user=user,
                password=password,
                **extra
            )
            conn.close()
            return True, None
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            if 'does not exist' in error_msg and 'database' in error_msg:
                # For synchronous UI flow, this is slightly problematic inside a worker thread
                # but we'll return a special error code
                return False, {"type": "db_not_found", "msg": error_msg}
            else:
                return False, {"type": "error", "msg": error_msg}
        except Exception as e:
            return False, {"type": "error", "msg": str(e)}

    def test_connection_impl(self):
        db_name = self.db_input.text()
        host = self.host_input.text()
        _cloud_domains = ["aivencloud.com", "elephantsql.com", "amazonaws.com", "heroku.com", "cloud.google.com"]
        is_cloud = any(d in host.lower() for d in _cloud_domains)
        _extra = {"sslmode": "require"} if is_cloud else {}
        
        is_uds = self.__class__.__name__ == "UDSConnectionDialog"

        if is_uds:
            # Run synchronously exactly as original
            try:
                conn = psycopg2.connect(
                    host=host,
                    port=int(self.port_input.text() or 5432),
                    database=db_name,
                    user=self.user_input.text(),
                    password=self.password_input.text(),
                    **_extra
                )
                conn.close()
                QMessageBox.information(self, "Success", "Connection successful!")
            except psycopg2.OperationalError as e:
                error_msg = str(e)
                if 'does not exist' in error_msg and 'database' in error_msg:
                    reply = QMessageBox.question(
                        self,
                        "Database Not Found",
                        f"The database '{db_name}' does not exist. Do you want to create it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        try:
                            conn_pg = psycopg2.connect(
                                host=self.host_input.text(),
                                port=int(self.port_input.text() or 5432),
                                database="postgres",
                                user=self.user_input.text(),
                                password=self.password_input.text()
                            )
                            conn_pg.autocommit = True
                            cursor = conn_pg.cursor()
                            cursor.execute(f'CREATE DATABASE \"{db_name}\"')
                            cursor.close()
                            conn_pg.close()
                            
                            conn_new = psycopg2.connect(
                                host=self.host_input.text(),
                                port=int(self.port_input.text() or 5432),
                                database=db_name,
                                user=self.user_input.text(),
                                password=self.password_input.text()
                            )
                            conn_new.close()
                            QMessageBox.information(self, "Success", f"Database '{db_name}' created and connection successful!")
                        except Exception as create_e:
                            QMessageBox.critical(self, "Error", f"Failed to create database:\n{create_e}")
                    else:
                        QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")
                else:
                    QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")
            return

        # Run asynchronously with loader for Postgres
        self.test_btn.start_loading("Testing")

        port = self.port_input.text()
        user = self.user_input.text()
        password = self.password_input.text()

        def _do_test():
            return self._run_connection_test(db_name, host, port, user, password, _extra)

        self._test_worker = WorkerThread(_do_test)
        self._test_worker.finished_signal.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, result, error):
        self.test_btn.stop_loading()
        db_name = self.db_input.text()

        if error:
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{error}")
            return

        success, err_data = result
        if success:
            QMessageBox.information(self, "Success", "Connection successful!")
        else:
            if err_data["type"] == "db_not_found":
                reply = QMessageBox.question(
                    self,
                    "Database Not Found",
                    f"The database '{db_name}' does not exist. Do you want to create it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        conn_pg = psycopg2.connect(
                            host=self.host_input.text(),
                            port=int(self.port_input.text() or 5432),
                            database="postgres",
                            user=self.user_input.text(),
                            password=self.password_input.text()
                        )
                        conn_pg.autocommit = True
                        cursor = conn_pg.cursor()
                        cursor.execute(f'CREATE DATABASE \"{db_name}\"')
                        cursor.close()
                        conn_pg.close()
                        
                        conn_new = psycopg2.connect(
                            host=self.host_input.text(),
                            port=int(self.port_input.text() or 5432),
                            database=db_name,
                            user=self.user_input.text(),
                            password=self.password_input.text()
                        )
                        conn_new.close()
                        QMessageBox.information(self, "Success", f"Database '{db_name}' created and connection successful!")
                    except Exception as create_e:
                        QMessageBox.critical(self, "Error", f"Failed to create database:\n{create_e}")
                else:
                    QMessageBox.critical(self, "Error", f"Failed to connect:\n{err_data['msg']}")
            else:
                QMessageBox.critical(self, "Error", f"Failed to connect:\n{err_data['msg']}")

    def save_connection_impl(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Connection name is required.")
            return
        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text(),
            "short_name": self.short_name_input.text(),
            "host": self.host_input.text(),
            "port": self.port_input.text(),
            "database": self.db_input.text(),
            "user": self.user_input.text(),
            "password": self.password_input.text(),
            "connection_group_id": self.group_combo.currentData()
        }