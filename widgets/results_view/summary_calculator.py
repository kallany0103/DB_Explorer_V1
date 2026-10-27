import math
import statistics
from typing import NamedTuple
from PySide6.QtCore import QModelIndex, Qt


class CellSummary(NamedTuple):
    total_count: int
    null_count: int
    non_null_count: int
    distinct_count: int
    numeric_count: int
    sum_val: float | None
    avg_val: float | None
    min_val: float | None
    max_val: float | None
    median_val: float | None
    stdev_val: float | None


def calculate_cell_summary(selected_indexes: list[QModelIndex]) -> CellSummary:
    """
    Computes statistical aggregates over selected table cell indexes.
    Parses numeric representations safely while accounting for nulls and distinct values.
    """
    total_count = len(selected_indexes)
    if total_count == 0:
        return CellSummary(0, 0, 0, 0, 0, None, None, None, None, None, None)

    null_count = 0
    distinct_values: set[str | None] = set()
    numeric_values: list[float] = []

    for idx in selected_indexes:
        val = idx.data(Qt.ItemDataRole.DisplayRole)
        if val is None or val == "" or str(val).strip().upper() == "NULL":
            null_count += 1
            distinct_values.add(None)
            continue

        str_val = str(val).strip()
        distinct_values.add(str_val)

        # Attempt to parse numeric value (handling commas, currency symbols, whitespace)
        cleaned = str_val.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
        try:
            num = float(cleaned)
            if not math.isnan(num) and not math.isinf(num):
                numeric_values.append(num)
        except (ValueError, TypeError):
            pass

    non_null_count = total_count - null_count
    numeric_count = len(numeric_values)

    sum_val = sum(numeric_values) if numeric_count > 0 else None
    avg_val = (sum_val / numeric_count) if (numeric_count > 0 and sum_val is not None) else None
    min_val = min(numeric_values) if numeric_count > 0 else None
    max_val = max(numeric_values) if numeric_count > 0 else None
    median_val = statistics.median(numeric_values) if numeric_count > 0 else None
    stdev_val = statistics.stdev(numeric_values) if numeric_count > 1 else None

    return CellSummary(
        total_count=total_count,
        null_count=null_count,
        non_null_count=non_null_count,
        distinct_count=len(distinct_values),
        numeric_count=numeric_count,
        sum_val=sum_val,
        avg_val=avg_val,
        min_val=min_val,
        max_val=max_val,
        median_val=median_val,
        stdev_val=stdev_val,
    )


def format_number(val: float | None, decimals: int = 2) -> str:
    """Formats a float with thousand separators and decimal places, stripping unnecessary zeros."""
    if val is None:
        return "N/A"
    if val.is_integer():
        return f"{int(val):,}"
    formatted = f"{val:,.{decimals}f}"
    return formatted


def format_summary_for_statusbar(summary: CellSummary) -> str:
    """Creates a concise TOAD-style summary line for the bottom status bar."""
    if summary.total_count == 0:
        return ""

    if summary.numeric_count > 0:
        parts = [
            f"Count: {summary.total_count:,}",
            f"Sum: {format_number(summary.sum_val)}",
            f"Avg: {format_number(summary.avg_val)}",
            f"Min: {format_number(summary.min_val)}",
            f"Max: {format_number(summary.max_val)}",
        ]
        if summary.null_count > 0:
            parts.append(f"Nulls: {summary.null_count:,}")
        return "   |   ".join(parts)

    return f"Count: {summary.total_count:,}   |   Distinct: {summary.distinct_count:,}   |   Nulls: {summary.null_count:,}"


def get_summary_display_rows(summary: CellSummary) -> list[tuple[str, str]]:
    """Returns key-value pairs of all metrics for tabular display in the summary dialog."""
    return [
        ("Total Cells", f"{summary.total_count:,}"),
        ("Non-Null Cells", f"{summary.non_null_count:,}"),
        ("Null Cells", f"{summary.null_count:,}"),
        ("Distinct Values", f"{summary.distinct_count:,}"),
        ("Numeric Cells", f"{summary.numeric_count:,}"),
        ("Sum", format_number(summary.sum_val, 4) if summary.numeric_count > 0 else "N/A"),
        ("Average (Mean)", format_number(summary.avg_val, 4) if summary.numeric_count > 0 else "N/A"),
        ("Minimum", format_number(summary.min_val, 4) if summary.numeric_count > 0 else "N/A"),
        ("Maximum", format_number(summary.max_val, 4) if summary.numeric_count > 0 else "N/A"),
        ("Median", format_number(summary.median_val, 4) if summary.numeric_count > 0 else "N/A"),
        ("Standard Deviation", format_number(summary.stdev_val, 4) if summary.stdev_val is not None else "N/A"),
    ]


def format_summary_for_clipboard(summary: CellSummary) -> str:
    """Formats the summary as tab-delimited text suitable for pasting into Excel or notes."""
    rows = get_summary_display_rows(summary)
    lines = ["Metric\tValue"]
    for metric, value in rows:
        lines.append(f"{metric}\t{value}")
    return "\n".join(lines)
