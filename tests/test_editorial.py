"""Tests for opinionated editorial workflow helpers."""

from __future__ import annotations

from rawtherapee_mcp.editorial import (
    build_critique_gate,
    build_curation_plan,
    build_editorial_brief,
    build_intent_inference_contract,
    editorial_candidate_parameters,
    safe_slug,
)


class TestSafeSlug:
    """Tests for safe_slug helper."""

    def test_slugifies_text(self):
        assert safe_slug("Warm Travel V1!") == "warm-travel-v1"

    def test_slug_fallback(self):
        assert safe_slug("###", fallback="candidate") == "candidate"


class TestBuildEditorialBrief:
    """Tests for strict brief contract."""

    def test_returns_expected_keys(self):
        brief = build_editorial_brief(
            "photo.cr2",
            intent="travel portrait",
            style="clean_editorial",
            output_goal="post_worthy",
        )

        expected_keys = {
            "file_path",
            "intent",
            "style",
            "output_goal",
            "recommended_workflow",
            "required_preview_loop_steps",
            "visual_critique_checklist",
            "rejection_criteria",
            "proof_only_criteria",
            "export_criteria",
            "style_specific_editing_priorities",
            "biggest_flaw_first_policy",
            "what_to_avoid",
            "rawtherapee_limitations",
            "llm_instructions",
        }
        assert expected_keys.issubset(set(brief.keys()))

    def test_contains_strict_instructions(self):
        brief = build_editorial_brief(
            "photo.cr2",
            intent=None,
            style="clean_editorial",
            output_goal="post_worthy",
        )
        instructions = brief["llm_instructions"]
        assert "Do not flatter mediocre results." in instructions
        assert "Fix the biggest flaw first." in instructions
        assert "If subject or face remains muddy, do not call the image finished." in instructions

    def test_includes_intent_aware_standard_when_inferred_intent_is_present(self):
        brief = build_editorial_brief(
            "photo.cr2",
            intent=None,
            style="clean_editorial",
            output_goal="post_worthy",
            inferred_intent={"primary_intent_category": "sunset_silhouette"},
        )
        assert brief["intent_standard"]["primary_intent_category"] == "sunset_silhouette"
        assert "preserve the reason this photo works" in " ".join(brief["visual_critique_checklist"]).lower()
        assert any("over-lift intentional darkness" in item for item in brief["llm_instructions"])


class TestEditorialCandidateParameters:
    """Tests for candidate parameter generation."""

    def test_candidate_styles_are_distinct(self):
        clean = editorial_candidate_parameters("clean_editorial")
        warm = editorial_candidate_parameters("warm_travel")
        cinematic = editorial_candidate_parameters("cinematic_soft")

        assert clean["white_balance"]["temperature"] != warm["white_balance"]["temperature"]
        assert warm["color_balance"]["enabled"] is True
        assert clean["tone_curve"]["curve"] != cinematic["tone_curve"]["curve"]
        assert cinematic["exposure"]["contrast"] < clean["exposure"]["contrast"]
        assert clean["luminance_curve"]["enabled"] is True
        assert warm["hsv_equalizer"]["enabled"] is True
        assert cinematic["highlight_rolloff"]["enabled"] is True

    def test_rt_510_disables_artifact_prone_microcontrast(self):
        clean = editorial_candidate_parameters("clean_editorial", rt_version="RawTherapee, version 5.10, command line.")

        assert clean["microcontrast"]["enabled"] is False
        assert "uniformity" not in clean["microcontrast"]
        assert clean["microcontrast"]["amount"] == 18
        assert clean["microcontrast"]["contrast"] == 20


class TestBuildCritiqueGate:
    """Tests for critique rubric builder."""

    def test_returns_required_rubric_and_threshold(self):
        gate = build_critique_gate("preview.jpg", candidate_name="cand1", intended_style="warm_travel")

        rubric = gate["scoring_rubric"]
        assert "subject_separation_score" in rubric
        assert "tonal_separation_score" in rubric
        assert "curve_quality_highlight_rolloff_score" in rubric
        assert "skin_orange_control_score" in rubric
        assert "green_grass_control_score" in rubric
        assert "sky_blue_control_score" in rubric
        assert "basic_adjustment_penalty" in rubric
        assert "overprocessing_penalty" in rubric
        assert "intent_alignment_score" in rubric
        assert "preserved_scene_value_score" in rubric
        assert "harmful_overcorrection_penalty" in rubric
        assert "wrong_standard_warning" in rubric
        assert "post_worthy_verdict" in rubric

        threshold = gate["minimum_export_threshold"]
        assert threshold["core_score_average_min"] == 7.0
        assert threshold["overprocessing_penalty_max"] == 3
        assert any("only changes exposure/warmth/saturation" in rule for rule in gate["next_action_rules"])

    def test_sunset_intent_does_not_force_dark_subject_as_automatic_failure(self):
        gate = build_critique_gate(
            "preview.jpg",
            candidate_name="cand1",
            intended_style="cinematic_soft",
            inferred_intent={"primary_intent_category": "sunset_silhouette"},
        )
        assert gate["intent_standard"]["subject_clarity_priority"] == "contextual"
        assert any("Dark subject is judged as failure only" in item for item in gate["automatic_failure_conditions"])
        assert any("Do not force bright portrait exposure" in rule for rule in gate["next_action_rules"])

    def test_clean_portrait_keeps_muddy_face_as_serious_failure(self):
        gate = build_critique_gate(
            "preview.jpg",
            candidate_name="cand1",
            intended_style="clean_editorial",
            inferred_intent={"primary_intent_category": "clean_portrait"},
        )
        assert gate["intent_standard"]["subject_clarity_priority"] == "critical"
        assert any("too dark or muddy for this intent" in item for item in gate["automatic_failure_conditions"])
        assert any("still too dark or muddy" in rule for rule in gate["next_action_rules"])


class TestBuildIntentInferenceContract:
    """Tests for intent inference contract builder."""

    def test_returns_expected_schema_and_categories(self):
        contract = build_intent_inference_contract(
            "photo.cr2",
            user_intent="travel memory",
            context_hint="sunset beach with person",
        )
        expected_keys = {
            "file_path",
            "user_intent",
            "context_hint",
            "required_visual_questions",
            "likely_intent_categories",
            "intent_model_schema",
            "preservation_targets",
            "possible_anti_fixes",
            "editing_strategy_guidance",
            "critique_standard_guidance",
            "output_contract",
            "next_recommended_tools",
        }
        assert expected_keys.issubset(set(contract.keys()))
        assert "sunset_silhouette" in contract["likely_intent_categories"]
        assert "studio_polished" in contract["likely_intent_categories"]
        assert "preview_raw" in contract["next_recommended_tools"]


class TestBuildCurationPlan:
    """Tests for curation planning helper."""

    def test_includes_rating_categories(self):
        plan = build_curation_plan(
            "/photos",
            intent="travel",
            recursive=True,
            max_files=50,
            discovered_files=["a.cr2", "b.nef"],
        )
        assert plan["discovered_file_count"] == 2
        assert "strong_keeper" in plan["rating_categories"]
        assert "reject" in plan["rating_categories"]
