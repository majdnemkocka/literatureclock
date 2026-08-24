#!/usr/bin/env python3
"""
Literature Clock TUI Dashboard & Workflow Automation Framework
Indítás: python dashboard_app.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.app import LiteratureClockDashboardApp


def main():
    app = LiteratureClockDashboardApp()
    app.run()


if __name__ == "__main__":
    main()
