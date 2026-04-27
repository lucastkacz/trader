"""Report export helpers."""

import json
import os
from datetime import datetime, timezone

from src.engine.trader.reporting.models import TradeReport
from src.engine.trader.reporting.render_markdown import render_markdown


def export_json(report: TradeReport) -> str:
    """Export report as JSON file. Returns the file path."""
    os.makedirs("data/reports", exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    path = f"data/reports/report_{ts}.json"
    with open(path, "w") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)
    return path


def export_markdown(report: TradeReport) -> str:
    """Export report as Markdown file. Returns the file path."""
    os.makedirs("data/reports", exist_ok=True)
    week_num = 1
    if report.uptime_hours > 0:
        week_num = max(1, int(report.uptime_hours / (24 * 7)) + 1)
    path = f"data/reports/weekly_report_week{week_num:02d}.md"
    with open(path, "w") as f:
        f.write(render_markdown(report))
    return path
