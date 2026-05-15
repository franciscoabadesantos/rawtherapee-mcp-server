"""Tests for manifest-backed autonomous control policy helpers."""

from __future__ import annotations

from rawtherapee_mcp.control_policy import (
    find_approved_curve,
    get_control_risk,
    get_approved_curve,
    is_control_allowed_autonomous,
    validate_autonomous_parameters,
)


class TestControlPolicy:
    def test_allowed_core_control_passes_within_manifest_range(self) -> None:
        assert is_control_allowed_autonomous("Exposure", "Contrast", 10)

    def test_allowed_core_control_fails_outside_manifest_range(self) -> None:
        assert not is_control_allowed_autonomous("Exposure", "Contrast", 80)

    def test_local_contrast_amount_is_blocked_for_autonomous(self) -> None:
        assert not is_control_allowed_autonomous("Local Contrast", "Amount", 0.1)

    def test_hsv_hcurve_is_blocked_for_autonomous(self) -> None:
        assert not is_control_allowed_autonomous("HSV Equalizer", "HCurve", "0;")

    def test_hsv_scurve_only_allows_approved_curve_values(self) -> None:
        assert is_control_allowed_autonomous("HSV Equalizer", "SCurve", "0;")
        assert not is_control_allowed_autonomous("HSV Equalizer", "SCurve", "0;0.1;1;")

    def test_approved_exposure_curve_passes_exact_value_validation(self) -> None:
        curve = get_approved_curve("tone_curve.midtone_pop_v1")
        assert curve is not None
        assert is_control_allowed_autonomous("Exposure", "CurveMode", curve["curve_mode"])
        assert is_control_allowed_autonomous("Exposure", "Curve", curve["curve_string"])
        assert is_control_allowed_autonomous("Exposure", "Curve2", curve["curve2"])

    def test_approved_tonal_depth_luminance_curve_fields_pass_exact_value_validation(self) -> None:
        preset = get_approved_curve("luminance_curve.landscape_depth_v1")
        assert preset is not None
        fields = preset["pp3_fields"]
        assert is_control_allowed_autonomous("Luminance Curve", "lhCurve", fields["Luminance Curve.lhCurve"])
        assert is_control_allowed_autonomous("Luminance Curve", "hhCurve", fields["Luminance Curve.hhCurve"])

    def test_arbitrary_exposure_curve_is_still_blocked(self) -> None:
        assert not is_control_allowed_autonomous("Exposure", "Curve", "3;0;0;0.5;0.7;1;1;")

    def test_arbitrary_luminance_curve_strings_are_still_blocked(self) -> None:
        assert not is_control_allowed_autonomous("Luminance Curve", "lhCurve", "3;0;0;0.5;0.7;1;1;")
        assert not is_control_allowed_autonomous("Luminance Curve", "hhCurve", "3;0;0;0.5;0.7;1;1;")

    def test_find_approved_curve_resolves_metadata_from_exact_value(self) -> None:
        curve = find_approved_curve("Exposure", "Curve", "3;0;0;0.45;0.52;1;1;")
        assert curve is not None
        assert curve["id"] == "tone_curve.midtone_pop_v1"

    def test_find_approved_curve_resolves_luminance_preset_metadata_from_exact_value(self) -> None:
        curve = find_approved_curve(
            "Luminance Curve",
            "lhCurve",
            "5;0;0;0.16;0.10;0.46;0.52;0.76;0.88;1;1;",
        )
        assert curve is not None
        assert curve["id"] == "luminance_curve.landscape_depth_v1"

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

    def test_validate_autonomous_parameters_blocks_arbitrary_curve_strings(self) -> None:
        result = validate_autonomous_parameters(
            {"tone_curve": {"curve_mode": "Standard", "curve": "3;0;0;0.5;0.7;1;1;", "curve2": "0;"}}
        )

        assert not result.allowed
        assert any(item.control_id == "Exposure.Curve" for item in result.blocked_controls)

    def test_validate_autonomous_parameters_blocks_modified_luminance_curve_strings(self) -> None:
        result = validate_autonomous_parameters(
            {
                "luminance_curve": {
                    "enabled": True,
                    "contrast": 10,
                    "avoid_color_shift": True,
                    "lh_curve": "5;0;0;0.18;0.13;0.50;0.52;0.78;0.86;1;1;",
                    "hh_curve": "5;0;0;0.30;0.28;0.62;0.56;0.84;0.80;1;0.94;",
                }
            }
        )

        assert not result.allowed
        assert any(item.control_id == "Luminance Curve.lhCurve" for item in result.blocked_controls)

    def test_validate_autonomous_parameters_blocks_out_of_range_values(self) -> None:
        result = validate_autonomous_parameters({"exposure": {"contrast": 80}})
        assert not result.allowed
        assert any(item.control_id == "Exposure.Contrast" for item in result.blocked_controls)
        assert any("outside suggested autonomous range" in item.reason for item in result.blocked_controls)

    def test_validate_autonomous_parameters_blocks_unknown_groups(self) -> None:
        result = validate_autonomous_parameters({"future_magic_control": {"value": 1}})
        assert not result.allowed
        assert any("Unknown parameter group" in item.reason for item in result.blocked_controls)

    def test_validate_autonomous_parameters_blocks_unknown_pp3_fields_in_known_group(self) -> None:
        result = validate_autonomous_parameters({"luminance_curve": {"mystery_field": "0;"}})
        assert not result.allowed
        assert any("Unknown control key" in item.reason for item in result.blocked_controls)

    def test_get_control_risk_returns_manifest_risks(self) -> None:
        risks = get_control_risk("HSV Equalizer", "HCurve")
        assert "broad color drift" in risks
