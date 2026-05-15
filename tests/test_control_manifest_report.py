"""Tests for control manifest report script."""

from __future__ import annotations

import subprocess
import sys


def test_manifest_report_script_runs() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/report_control_manifest.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "RawTherapee Control Manifest Report" in result.stdout
    assert "allowed autonomous controls" in result.stdout
    assert "pending_evidence controls" in result.stdout
