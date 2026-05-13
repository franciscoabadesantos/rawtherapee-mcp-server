"""Tests for reusable safe editing techniques."""

from __future__ import annotations

from rawtherapee_mcp.editing_techniques import (
    TECHNIQUE_REGISTRY,
    combine_techniques,
    technique_risk_tags,
    technique_to_parameters,
)


class TestTechniqueRegistry:
    def test_registry_contains_core_techniques(self):
        expected = {
            "gentle_s_curve",
            "clean_midtone_contrast",
            "soft_highlight_rolloff",
            "subtle_shadow_depth",
            "subject_readability_without_hdr",
            "preserve_silhouette_tone",
            "muted_fog_contrast",
            "shape_light_break_tonality",
            "subtle_water_luma_depth",
            "controlled_blue_presence",
            "natural_green_compression",
            "reduce_green_gray_cast_safe",
            "skin_safe_warmth",
            "clean_neutral_balance",
            "preserve_material_texture",
            "calm_global_saturation",
            "gentle_structure_without_crunch",
        }
        assert expected.issubset(set(TECHNIQUE_REGISTRY))

    def test_technique_outputs_are_safe_dicts(self):
        for name in TECHNIQUE_REGISTRY:
            params = technique_to_parameters(name)
            assert isinstance(params, dict)
            assert "color_balance" not in params
            assert "split_toning" not in params
            microcontrast = params.get("microcontrast", {})
            if isinstance(microcontrast, dict):
                assert "uniformity" not in microcontrast

    def test_registry_exposes_expected_risk_tags(self):
        assert set(technique_risk_tags("controlled_blue_presence")) == {"cyan_shift", "blue_split", "synthetic_blue"}
        assert set(technique_risk_tags("skin_safe_warmth")) == {"warm_shift", "orange_shift"}
        assert set(technique_risk_tags("natural_green_compression")) == {"hue_shift", "green_shift"}


class TestCombineTechniques:
    def test_merges_and_tracks_overwrites(self):
        merged = combine_techniques(
            [
                "gentle_s_curve",
                "soft_highlight_rolloff",
                "gentle_s_curve",
                "unknown_name",
            ]
        )
        assert "tone_curve" in merged["parameters"]
        assert "highlight_rolloff" in merged["parameters"]
        assert "unknown_name" in merged["unknown_techniques"]
        assert any(name.startswith("tone_curve.") for name in merged["overwritten_parameters"])
