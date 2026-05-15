"""Tests for manifest-backed autonomous control policy helpers."""

from __future__ import annotations

from rawtherapee_mcp.control_policy import (
    get_control_risk,
    is_control_allowed_autonomous,
    validate_autonomous_parameters,
)


class TestControlPolicy:
    def test_local_contrast_amount_is_blocked_for_autonomous(self) -> None:
        assert not is_control_allowed_autonomous("Local Contrast", "Amount", 0.1)

    def test_hsv_hcurve_is_blocked_for_autonomous(self) -> None:
        assert not is_control_allowed_autonomous("HSV Equalizer", "HCurve", "0;")

    def test_hsv_scurve_only_allows_approved_curve_values(self) -> None:
        assert is_control_allowed_autonomous("HSV Equalizer", "SCurve", "0;")
        assert not is_control_allowed_autonomous("HSV Equalizer", "SCurve", "0;0.1;1;")

    def test_unknown_controls_default_to_manual_only(self) -> None:
        assert not is_control_allowed_autonomous("Unknown Section", "Unknown Key", 1)

    def test_validate_autonomous_parameters_blocks_known_dangerous_primitives(self) -> None:
        result = validate_autonomous_parameters(
            {
                "local_contrast": {"amount": 1},
                "hsv_equalizer": {"h_curve": "0;"},
            }
        )

        assert not result.allowed
        blocked_ids = {item.control_id for item in result.blocked_controls}
        assert "Local Contrast.Amount" in blocked_ids
        assert "HSV Equalizer.HCurve" in blocked_ids

    def test_validate_autonomous_parameters_blocks_unknown_groups(self) -> None:
        result = validate_autonomous_parameters({"future_magic_control": {"value": 1}})
        assert not result.allowed
        assert any("Unknown parameter group" in item.reason for item in result.blocked_controls)

    def test_get_control_risk_returns_manifest_risks(self) -> None:
        risks = get_control_risk("HSV Equalizer", "HCurve")
        assert "broad color drift" in risks
