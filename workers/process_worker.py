# workers/process_worker.py
import uuid
import time
from PySide6.QtCore import QObject, QProcess, Signal

class ProcessSignals(QObject):
    """Signals for the asynchronous process worker."""
    started = Signal(str, dict)       # process_id, metadata
    output = Signal(str, str)        # process_id, text
    error = Signal(str, str)         # process_id, message
    finished = Signal(str, str, float, int) # process_id, message, elapsed_time, row_count

class ProcessWorker(QObject):
    """
    Executes external commands (like pg_dump) using QProcess.
    This ensures that the OS shell doesn't block the UI.
    """
    def __init__(self, command, args, metadata=None, env=None):
        super().__init__()
        self.command = command
        self.args = args
        self.metadata = metadata or {}
        self.env = env
        self.process_id = str(uuid.uuid4())[:8]
        self.signals = ProcessSignals()
        
        self.process = QProcess()
        if self.env:
            self.process.setProcessEnvironment(self.env)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_finished)
        
        self.start_time = None

    def run(self):
        """Starts the process."""
        self.start_time = time.time()
        self.signals.started.emit(self.process_id, self.metadata)
        
        # Start the process
        self.process.start(self.command, self.args)
        
        if not self.process.waitForStarted():
            err_msg = f"Failed to start process: {self.command}"
            self.signals.error.emit(self.process_id, err_msg)
            self.signals.finished.emit(self.process_id, err_msg, 0.0, 0)

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        if data:
            self.signals.output.emit(self.process_id, data)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode()
        if data:
            # Often pg_dump sends progress/info to stderr, so we treat it as output/info unless it's a crash
            self.signals.output.emit(self.process_id, data)

    def handle_finished(self, exit_code, exit_status):
        elapsed = time.time() - self.start_time
        if exit_code == 0:
            self.signals.finished.emit(self.process_id, "Process completed successfully.", elapsed, 0)
        else:
            # Read any remaining stderr output before signalling error
            remaining = self.process.readAllStandardError().data().decode().strip()
            err = remaining or f"Process exited with code {exit_code}"
            # Only emit error — do NOT also emit finished, as that would overwrite the Error status
            self.signals.error.emit(self.process_id, err)

    def cancel(self):
        """Terminates the running process."""
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(2000):
                self.process.kill()
