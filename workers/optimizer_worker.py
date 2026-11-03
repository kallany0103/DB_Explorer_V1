"""workers/optimizer_worker.py

Background workers for asynchronous SQL query plan cost evaluation,
empirical execution benchmarking, and virtual index simulation.
"""

from typing import List, Optional

from PySide6.QtCore import QObject, QRunnable, Signal

from db.optimizer.batch import BatchOptimizationSummary, analyze_batch_workload
from db.optimizer.benchmarker import benchmark_variants
from db.optimizer.cost_evaluator import evaluate_variant_costs
from db.optimizer.variants import QueryVariant
from db.optimizer.virtual_index import VirtualIndexResult, simulate_index


class OptimizerSignals(QObject):
    """Signals for optimizer cost evaluation worker."""

    finished = Signal(list)
    error = Signal(str)


class OptimizerCostWorker(QRunnable):
    """Executes database plan cost evaluation in a background worker thread."""

    def __init__(
        self,
        variants: List[QueryVariant],
        conn_data: Optional[dict] = None,
    ):
        super().__init__()
        self.variants = variants
        self.conn_data = conn_data
        self.signals = OptimizerSignals()

    def run(self) -> None:
        try:
            evaluated = evaluate_variant_costs(self.variants, self.conn_data)
            self.signals.finished.emit(evaluated)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class BenchmarkSignals(QObject):
    """Signals for empirical execution benchmark worker."""

    finished = Signal(list)
    error = Signal(str)


class BenchmarkWorker(QRunnable):
    """Empirically executes variants with strict statement timeouts."""

    def __init__(
        self,
        variants: List[QueryVariant],
        conn_data: Optional[dict] = None,
        timeout_sec: float = 3.0,
    ):
        super().__init__()
        self.variants = variants
        self.conn_data = conn_data
        self.timeout_sec = timeout_sec
        self.signals = BenchmarkSignals()

    def run(self) -> None:
        try:
            results = benchmark_variants(self.variants, self.conn_data, self.timeout_sec)
            self.signals.finished.emit(results)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class VirtualIndexSignals(QObject):
    """Signals for virtual index simulation worker."""

    finished = Signal(object)  # VirtualIndexResult
    error = Signal(str)


class VirtualIndexWorker(QRunnable):
    """Simulates hypothetical indexes without physical disk allocation."""

    def __init__(
        self,
        index_ddl: str,
        query_sql: str,
        conn_data: Optional[dict] = None,
    ):
        super().__init__()
        self.index_ddl = index_ddl
        self.query_sql = query_sql
        self.conn_data = conn_data
        self.signals = VirtualIndexSignals()

    def run(self) -> None:
        try:
            res: VirtualIndexResult = simulate_index(
                self.index_ddl, self.query_sql, self.conn_data
            )
            self.signals.finished.emit(res)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class BatchOptimizerSignals(QObject):
    """Signals for workload-wide batch query optimization worker."""

    finished = Signal(object)  # BatchOptimizationSummary
    error = Signal(str)


class BatchOptimizerWorker(QRunnable):
    """Executes multi-statement script analysis asynchronously."""

    def __init__(
        self,
        script_text: str,
        dialect: str = "postgres",
        conn_data: Optional[dict] = None,
    ):
        super().__init__()
        self.script_text = script_text
        self.dialect = dialect
        self.conn_data = conn_data
        self.signals = BatchOptimizerSignals()

    def run(self) -> None:
        try:
            summary: BatchOptimizationSummary = analyze_batch_workload(
                self.script_text, self.dialect, self.conn_data
            )
            self.signals.finished.emit(summary)
        except Exception as exc:
            self.signals.error.emit(str(exc))

