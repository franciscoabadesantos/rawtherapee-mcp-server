"""Tests for opinionated editorial workflow helpers."""

from __future__ import annotations

from rawtherapee_mcp.editorial import (
    build_critique_gate,
    build_curation_plan,
    build_editorial_brief,
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


class TestEditorialCandidateParameters:
    """Tests for candidate parameter generation."""

    def test_candidate_styles_are_distinct(self):
        clean = editorial_candidate_parameters("clean_editorial")
        warm = editorial_candidate_parameters("warm_travel")
        cinematic = editorial_candidate_parameters("cinematic_soft")

        assert clean["white_balance"]["temperature"] != warm["white_balance"]["temperature"]
        assert warm["exposure"]["saturation"] > clean["exposure"]["saturation"]
        assert cinematic["exposure"]["contrast"] < clean["exposure"]["contrast"]


class TestBuildCritiqueGate:
    """Tests for critique rubric builder."""

    def test_returns_required_rubric_and_threshold(self):
        gate = build_critique_gate("preview.jpg", candidate_name="cand1", intended_style="warm_travel")

        rubric = gate["scoring_rubric"]
        assert "subject_separation_score" in rubric
        assert "overprocessing_penalty" in rubric
        assert "post_worthy_verdict" in rubric

        threshold = gate["minimum_export_threshold"]
        assert threshold["core_score_average_min"] == 7.0
        assert threshold["overprocessing_penalty_max"] == 3


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
