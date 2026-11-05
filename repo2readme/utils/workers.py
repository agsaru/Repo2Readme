"""Validate and resolve the worker count shared by traversal and summarization."""

from __future__ import annotations

DEFAULT_MAX_WORKERS = 4

MIN_MAX_WORKERS = 1


def validate_max_workers(value: int | None) -> int | None:
    """Return a valid worker count, leaving None for the default."""
    if value is None:
        return None

    if value < MIN_MAX_WORKERS:
        raise ValueError(
            f"must be {MIN_MAX_WORKERS} or greater, got {value}"
        )

    return value


def resolve_worker_count(
    requested: int | None,
    total_items: int,
    default: int = DEFAULT_MAX_WORKERS,
) -> int:
    """Resolve the worker count without exceeding the amount of work."""
    wanted = default if requested is None else requested
    wanted = max(MIN_MAX_WORKERS, wanted)

    if total_items <= 0:
        return MIN_MAX_WORKERS

    return min(wanted, total_items)
