import time


def perf_now():
    return time.perf_counter()


def perf_elapsed_ms(start):
    if start is None:
        return None
    return (time.perf_counter() - start) * 1000.0


def perf_record(owner, name, value):
    if value is None:
        return
    if not hasattr(owner, "perf_metrics"):
        owner.perf_metrics = {}
    bucket = owner.perf_metrics.setdefault(name, [])
    bucket.append(float(value))
    if len(bucket) > 200:
        del bucket[:-200]


def perf_mark(owner, key):
    if not hasattr(owner, "_perf_marks"):
        owner._perf_marks = {}
    owner._perf_marks[key] = perf_now()


def perf_take(owner, key):
    marks = getattr(owner, "_perf_marks", None)
    if not marks:
        return None
    return marks.pop(key, None)


def _percentile(values, p):
    if not values:
        return None
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    rank = (len(sorted_vals) - 1) * float(p)
    low = int(rank)
    high = min(low + 1, len(sorted_vals) - 1)
    fraction = rank - low
    return float(sorted_vals[low] + (sorted_vals[high] - sorted_vals[low]) * fraction)


def perf_snapshot(owner):
    metrics = getattr(owner, "perf_metrics", {}) or {}
    snapshot = {}
    for name, series in metrics.items():
        if not series:
            continue
        values = [float(x) for x in series]
        count = len(values)
        snapshot[name] = {
            "count": count,
            "last": float(values[-1]),
            "avg": float(sum(values) / count),
            "min": float(min(values)),
            "max": float(max(values)),
            "p95": _percentile(values, 0.95),
        }
    return snapshot
