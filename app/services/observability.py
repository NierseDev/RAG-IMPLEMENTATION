"""
Optional observability helpers.

LangSmith tracing is used when installed and enabled; otherwise these helpers
degrade to structured logging so local/dev setups keep working.
"""
from __future__ import annotations

from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


def build_run_metadata(**kwargs: Any) -> Dict[str, Any]:
    """Drop empty metadata values so traces stay compact."""
    return {key: value for key, value in kwargs.items() if value is not None}


def traceable(*, name: str, run_type: str = "chain"):
    """Return a LangSmith trace decorator when available, else no-op."""
    try:
        from langsmith import traceable as langsmith_traceable
    except Exception:
        def decorator(func):
            return func

        return decorator

    return langsmith_traceable(name=name, run_type=run_type)


def log_run(name: str, metadata: Dict[str, Any]) -> None:
    """Log structured run metadata for local debugging."""
    if metadata:
        logger.info("trace[%s] %s", name, metadata)
