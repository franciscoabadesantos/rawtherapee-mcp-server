"""Tests for advanced tone and color parameter helpers."""

from __future__ import annotations

from rawtherapee_mcp.advanced_color import (
    cinematic_soft_color_separation,
    clean_midtone_contrast,
    clean_sky_blue,
    gentle_s_curve,
    merge_parameter_sets,
    natural_green_control,
    protect_skin_reduce_orange,
    reduce_green_gray_cast,
    soft_highlight_rolloff,
    warm_highlights_cool_shadows,
    warm_sand_preserve_skin,
)


class TestMergeParameterSets:
    """Tests for deep grouped merge behavior."""

    def test_merges_groups_without_losing_values(self):
        merged = merge_parameter_sets(
            {"exposure": {"contrast": 10}},
            {"exposure": {"saturation": 4}, "vibrance": {"enabled": True}},
        )
        assert merged["exposure"]["contrast"] == 10
        assert merged["exposure"]["saturation"] == 4
        assert merged["vibrance"]["enabled"] is True


class TestAdvancedHelpers:
    """Tests for individual helper output contracts."""

    def test_gentle_s_curve_has_tone_curve_group(self):
        params = gentle_s_curve()
        assert "tone_curve" in params
        assert "curve" in params["tone_curve"]

    def test_clean_midtone_contrast_enables_luminance_curve(self):
        params = clean_midtone_contrast()
        assert params["luminance_curve"]["enabled"] is True
        assert "lh_curve" in params["luminance_curve"]

    def test_soft_highlight_rolloff_enables_hl_recovery_controls(self):
        params = soft_highlight_rolloff()
        assert params["highlight_rolloff"]["enabled"] is True
        assert params["highlight_rolloff"]["method"] == "Coloropp"

    def test_warm_highlights_cool_shadows_returns_color_balance(self):
        params = warm_highlights_cool_shadows()
        assert params["color_balance"]["enabled"] is True
        assert "red_high" in params["color_balance"]
        assert "blue_low" in params["color_balance"]

    def test_skin_and_orange_protection_uses_vibrance_and_hsv(self):
        params = protect_skin_reduce_orange()
        assert params["vibrance"]["protectskins"] is True
        assert params["hsv_equalizer"]["enabled"] is True

    def test_sky_and_green_helpers_use_hsv(self):
        sky = clean_sky_blue()
        green = natural_green_control()
        assert sky["hsv_equalizer"]["enabled"] is True
        assert green["hsv_equalizer"]["enabled"] is True

    def test_reduce_green_gray_cast_has_luminance_curve_guardrails(self):
        params = reduce_green_gray_cast()
        assert params["luminance_curve"]["avoid_color_shift"] is True

    def test_warm_sand_preserve_skin_merges_color_balance_and_vibrance(self):
        params = warm_sand_preserve_skin()
        assert "color_balance" in params
        assert "vibrance" in params

    def test_cinematic_soft_color_separation_has_multiple_advanced_groups(self):
        params = cinematic_soft_color_separation()
        assert "tone_curve" in params
        assert "highlight_rolloff" in params
        assert "color_balance" in params
