"""Tests for structured PP3 diff analysis."""

from __future__ import annotations

from pathlib import Path

from rawtherapee_mcp.pp3_diff import analyze_pp3_diff


def _write_pp3(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


class TestAnalyzePp3Diff:
    def test_reports_single_key_change(self, tmp_path: Path) -> None:
        before = tmp_path / "before.pp3"
        after = tmp_path / "after.pp3"

        _write_pp3(
            before,
            "[Version]\nAppVersion=5.11\nVersion=351\n\n[Exposure]\nCompensation=0\nContrast=0\n",
        )
        _write_pp3(
            after,
            "[Version]\nAppVersion=5.11\nVersion=351\n\n[Exposure]\nCompensation=0.5\nContrast=0\n",
        )

        result = analyze_pp3_diff(before, after)

        assert len(result["changed"]) == 1
        assert result["changed"][0] == {
            "section": "Exposure",
            "key": "Compensation",
            "before": "0",
            "after": "0.5",
        }
        assert result["added"] == []
        assert result["removed"] == []
        assert "possible_noise" in result

    def test_flags_crop_as_possible_noise(self, tmp_path: Path) -> None:
        before = tmp_path / "before.pp3"
        after = tmp_path / "after.pp3"

        _write_pp3(before, "[Crop]\nEnabled=false\n")
        _write_pp3(after, "[Crop]\nEnabled=true\nX=0\nY=0\nW=4000\nH=3000\n")

        result = analyze_pp3_diff(before, after)

        assert any(item["section"] == "Crop" for item in result["possible_noise"])
