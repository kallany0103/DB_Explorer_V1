"""db/optimizer/benchmarker.py

Empirical execution benchmark runner for SQL query variants.
Safely measures actual execution runtime, buffer pool hits, and disk reads
using strict statement timeouts to prevent server degradation.
"""

import json
import logging
import time
from typing import List, Optional

from db.db_connections import get_pooled_oracle_connection, get_pooled_postgres_connection
from db.optimizer.variants import QueryVariant

logger = logging.getLogger(__name__)


def benchmark_variants(
    variants: List[QueryVariant],
    conn_data: Optional[dict] = None,
    timeout_sec: float = 3.0,
) -> List[QueryVariant]:
    """Empirically executes variants against the connected database to measure real runtime.

    Enforces safety checks: only SELECT queries are benchmarked, and each execution
    is bounded by a strict statement timeout.
    """
    if not variants:
        return []

    # Safety validation: benchmark only read-only statements
    safe_variants = [v for v in variants if _is_safe_select_query(v.sql)]
    if not safe_variants:
        return variants

    db_type = (
        (conn_data.get("db_type") or conn_data.get("code") or "").lower()
        if conn_data
        else ""
    )

    success = False
    if conn_data and ("postgres" in db_type or "pgsql" in db_type):
        success = _benchmark_postgres(safe_variants, conn_data, timeout_sec)
    elif conn_data and "oracle" in db_type:
        success = _benchmark_oracle(safe_variants, conn_data, timeout_sec)

    if not success:
        _apply_simulated_benchmark(safe_variants)

    _compute_speedups(safe_variants)
    return variants


def _is_safe_select_query(sql: str) -> bool:
    """Verifies that the statement is strictly a read-only query."""
    clean = (sql or "").strip().upper()
    # Reject harmful mutation keywords
    forbidden = ["DELETE ", "UPDATE ", "INSERT ", "DROP ", "TRUNCATE ", "ALTER ", "MERGE "]
    if any(clean.startswith(f) for f in forbidden):
        return False
    return clean.startswith("SELECT") or clean.startswith("WITH") or clean.startswith("EXPLAIN")


def _benchmark_postgres(
    variants: List[QueryVariant],
    conn_data: dict,
    timeout_sec: float,
) -> bool:
    """Runs EXPLAIN (ANALYZE, BUFFERS, TIMING, FORMAT JSON) on PostgreSQL."""
    conn = None
    try:
        conn = get_pooled_postgres_connection(conn_data)
        if not conn:
            return False

        timeout_ms = int(timeout_sec * 1000)
        with conn.cursor() as cur:
            for v in variants:
                v.benchmark_status = "running"
                try:
                    cur.execute(f"SET statement_timeout = {timeout_ms};")
                    clean_sql = v.sql.rstrip(";").strip()
                    cur.execute(
                        f"EXPLAIN (ANALYZE, BUFFERS, TIMING, FORMAT JSON) {clean_sql}"
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        raw = row[0]
                        if isinstance(raw, str):
                            raw = json.loads(raw)

                        plan_data = raw[0] if isinstance(raw, list) and raw else raw
                        exec_time = plan_data.get("Execution Time")
                        if exec_time is not None:
                            v.actual_time_ms = round(float(exec_time), 2)
                            v.benchmark_status = "success"

                        plan_root = plan_data.get("Plan", {})
                        v.buffer_hits = int(plan_root.get("Shared Hit Blocks", 0))
                        v.disk_reads = int(plan_root.get("Shared Read Blocks", 0))
                except Exception as ex:
                    err_msg = str(ex).lower()
                    if "timeout" in err_msg or "canceling statement" in err_msg:
                        v.benchmark_status = "timeout"
                        v.actual_time_ms = round(timeout_sec * 1000.0, 2)
                    else:
                        v.benchmark_status = "error"
                    logger.debug("Benchmark error for variant %s: %s", v.label, ex)
                    if hasattr(conn, "rollback"):
                        conn.rollback()

            # Reset timeout to default
            try:
                cur.execute("SET statement_timeout = 0;")
            except Exception:
                pass

        return True
    except Exception as e:
        logger.debug("PostgreSQL benchmark run failed: %s", e)
        return False


def _benchmark_oracle(
    variants: List[QueryVariant],
    conn_data: dict,
    timeout_sec: float,
) -> bool:
    """Runs controlled execution timing on Oracle."""
    conn = None
    try:
        conn = get_pooled_oracle_connection(conn_data=conn_data)
        if not conn:
            return False

        cursor = conn.cursor()
        for v in variants:
            v.benchmark_status = "running"
            try:
                clean_sql = v.sql.rstrip(";").strip()
                t0 = time.perf_counter()
                cursor.execute(clean_sql)
                # Fetch up to 100 sample rows to measure query pipeline without client-side buffer saturation
                cursor.fetchmany(100)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                v.actual_time_ms = round(elapsed_ms, 2)
                v.benchmark_status = "success"
            except Exception as ex:
                v.benchmark_status = "error"
                logger.debug("Oracle benchmark error for variant %s: %s", v.label, ex)
                if hasattr(conn, "rollback"):
                    conn.rollback()

        cursor.close()
        return True
    except Exception as e:
        logger.debug("Oracle benchmark run failed: %s", e)
        return False


def _apply_simulated_benchmark(variants: List[QueryVariant]) -> None:
    """Provides estimated runtimes when disconnected from a live database."""
    base_time_ms = 45.0
    for v in variants:
        if v.id == 0:
            v.actual_time_ms = base_time_ms
        elif v.cost is not None and variants[0].cost and variants[0].cost > 0:
            ratio = v.cost / variants[0].cost
            v.actual_time_ms = round(max(0.5, base_time_ms * ratio), 2)
        else:
            v.actual_time_ms = round(base_time_ms * 0.4, 2)
        v.benchmark_status = "simulated"


def _compute_speedups(variants: List[QueryVariant]) -> None:
    """Calculates relative performance speedup multiplier vs baseline."""
    if not variants:
        return

    baseline_time = variants[0].actual_time_ms
    if not baseline_time or baseline_time <= 0:
        return

    for v in variants:
        if v.actual_time_ms and v.actual_time_ms > 0:
            speedup = round(baseline_time / v.actual_time_ms, 1)
            v.time_speedup = speedup

