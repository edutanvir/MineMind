"""The trace panel's pure helper. Does not need Streamlit or the database."""
import pytest

pytest.importorskip("duckdb")
from src.ui.trace_panel import summarize_trace  # noqa: E402


def test_empty_log_means_no_tools_were_used():
    info = summarize_trace([])
    assert info["calls"] == 0 and info["datasets"] == []


def test_summary_counts_rows_errors_and_unique_datasets():
    log = [
        {"tool": "search_mines", "args": {"commodity": "nickel"}, "rows": 10, "error": None},
        {"tool": "mines_near_place", "args": {"place": "Sudbury"}, "rows": 5, "error": None},
        {"tool": "get_production_trend", "args": {}, "rows": 0, "error": "Unknown measure."},
    ]
    info = summarize_trace(log)
    assert info["calls"] == 3 and info["rows"] == 15
    assert len(info["errors"]) == 1
    assert len(info["datasets"]) == 2        # NRCan once, StatCan once
