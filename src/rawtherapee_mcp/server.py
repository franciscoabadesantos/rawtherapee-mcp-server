"""RawTherapee MCP Server — FastMCP entrypoint.

Registers all tool modules and starts the STDIO server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import time
from collections.abc import AsyncIterator
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fastmcp import Context, FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.tools import ToolResult
from fastmcp.utilities.types import Image as MCPImage
from mcp.types import ImageContent, TextContent
from PIL import Image as PILImage

from rawtherapee_mcp import __version__
from rawtherapee_mcp.advanced_color import merge_parameter_sets
from rawtherapee_mcp.config import RTConfig, load_config
from rawtherapee_mcp.control_policy import build_agent_manifest_summary, validate_autonomous_parameters
from rawtherapee_mcp.device_presets import (
    add_custom_preset,
    delete_custom_preset,
    get_all_presets,
    get_preset,
    is_builtin_preset,
)
from rawtherapee_mcp.editorial import (
    build_candidate_descriptor,
    build_critique_gate,
    build_curation_plan,
    build_editorial_brief,
    build_intent_inference_contract,
    editorial_candidate_parameters,
    ensure_existing_file,
    safe_slug,
)
from rawtherapee_mcp.exif_reader import (
    generate_recommendations,
    get_effective_dimensions,
    read_exif_data,
)
from rawtherapee_mcp.exif_reader import get_image_info as _get_image_info
from rawtherapee_mcp.histogram import compute_histogram, render_histogram_svg
from rawtherapee_mcp.image_utils import generate_thumbnail
from rawtherapee_mcp.lensfun import check_lens_support as _check_lens_support
from rawtherapee_mcp.locallab import (
    add_spot,
    apply_preset,
    get_spot_count,
    read_spot,
    remove_spot,
    update_spot,
)
from rawtherapee_mcp.locallab import (
    get_preset as get_local_preset,
)
from rawtherapee_mcp.locallab import (
    list_presets as list_local_presets,
)
from rawtherapee_mcp.metadata import inspect_metadata as _inspect_metadata
from rawtherapee_mcp.metadata import set_metadata as _set_metadata
from rawtherapee_mcp.metadata import strip_metadata as _strip_metadata
from rawtherapee_mcp.pp3_generator import (
    _load_template,
    apply_device_crop,
    apply_parameters,
    create_neutral_profile,
    sanitize_autonomous_parameters,
)
from rawtherapee_mcp.pp3_generator import generate_profile as _generate_profile
from rawtherapee_mcp.pp3_parser import PP3Profile
from rawtherapee_mcp.predictive_editor import (
    build_manifest_select_edit_plan,
    build_predictive_edit_plan,
    score_predictive_export_decision,
)
from rawtherapee_mcp.profile_hierarchy import create_variant as _create_variant
from rawtherapee_mcp.profile_hierarchy import list_variants as _list_variants
from rawtherapee_mcp.profile_hierarchy import propagate_to_variants as _propagate_to_variants
from rawtherapee_mcp.rt_cli import get_rt_version, run_rt_cli
from rawtherapee_mcp.visual_intent import (
    build_composition_plan,
    build_crop_candidate_specs,
    build_editing_vision_contract,
    build_vision_candidate_specs,
    resolve_visual_moves,
    validate_filled_editing_vision,
)
from rawtherapee_mcp.visual_intent import (
    list_visual_editing_moves as build_visual_move_list,
)
from rawtherapee_mcp.visual_intent import (
    visual_moves_to_parameter_plan as map_visual_moves_to_parameter_plan,
)
from rawtherapee_mcp.visual_intent import (
    visual_moves_to_parameters as map_visual_moves_to_parameters,
)

logger = logging.getLogger("rawtherapee_mcp")

# Supported RAW file extensions (case-insensitive)
RAW_EXTENSIONS = frozenset(
    {
        ".cr2",
        ".cr3",
        ".nef",
        ".nrw",
        ".arw",
        ".srf",
        ".sr2",
        ".raf",
        ".orf",
        ".rw2",
        ".rwl",
        ".dng",
        ".pef",
        ".ptx",
        ".3fr",
        ".fff",
        ".iiq",
        ".mrw",
        ".mef",
        ".mos",
        ".kdc",
        ".dcr",
        ".raw",
        ".srw",
        ".x3f",
        ".erf",
    }
)

_NON_OVERRIDEABLE_GATE_MESSAGE = (
    "The verification gate is not a suggestion. This decision means the edit did not meet export quality "
    "requirements. The agent must not override this decision. Generate a new edit through "
    "auto_edit_manifest_select_prepare, or accept the non-export result."
)


def _get_templates_dir() -> Path:
    """Get the path to built-in PP3 templates."""
    return Path(str(files("rawtherapee_mcp.templates")))


def _verification_marker_dir(config: RTConfig) -> Path:
    marker_dir = config.preview_dir / "_verification_markers"
    marker_dir.mkdir(parents=True, exist_ok=True)
    return marker_dir


def _profile_signature(profile_path: Path) -> dict[str, Any]:
    stat = profile_path.stat()
    return {
        "profile_path": str(profile_path.resolve()),
        "profile_mtime_ns": stat.st_mtime_ns,
        "profile_size": stat.st_size,
    }


def _profile_requires_verification(config: RTConfig, profile_path: Path) -> bool:
    resolved = profile_path.resolve()
    guarded_roots = [config.custom_templates_dir.resolve(), config.preview_dir.resolve()]
    return any(resolved.is_relative_to(root) for root in guarded_roots)


def _write_verification_marker(
    config: RTConfig,
    *,
    raw_path: Path,
    profile_path: Path,
    decision: str,
    export_gate_passed: bool,
    decision_source: str,
) -> dict[str, Any]:
    verification_id = uuid4().hex
    marker = {
        "verification_id": verification_id,
        "decision": decision,
        "decision_source": decision_source,
        "export_gate_passed": bool(export_gate_passed),
        "verified_export_allowed": bool(export_gate_passed and decision == "export"),
        "raw_path": str(raw_path.resolve()),
        **_profile_signature(profile_path),
        "created_at_epoch_ms": int(time.time() * 1000),
    }
    marker_path = _verification_marker_dir(config) / f"{verification_id}.json"
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    return marker


def _load_verification_marker(config: RTConfig, verification_id: str) -> dict[str, Any] | None:
    marker_path = _verification_marker_dir(config) / f"{verification_id}.json"
    if not marker_path.is_file():
        return None
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _validate_export_verification(
    config: RTConfig,
    *,
    raw_path: Path,
    profile_path: Path,
    verification_id: str | None,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    if not verification_id:
        return False, None, "Missing verification_id for an autonomous/generated profile."
    marker = _load_verification_marker(config, verification_id)
    if marker is None:
        return False, None, f"Verification marker not found: {verification_id}"
    if not marker.get("verified_export_allowed"):
        return False, marker, "Verification marker exists but does not authorize export."
    if str(marker.get("raw_path")) != str(raw_path.resolve()):
        return False, marker, "Verification marker raw_path does not match the requested RAW file."
    current_signature = _profile_signature(profile_path)
    if str(marker.get("profile_path")) != current_signature["profile_path"]:
        return False, marker, "Verification marker profile_path does not match the requested profile."
    if marker.get("profile_mtime_ns") != current_signature["profile_mtime_ns"]:
        return False, marker, "Profile has changed since verification; rerun verify_predictive_edit."
    if marker.get("profile_size") != current_signature["profile_size"]:
        return False, marker, "Profile content changed since verification; rerun verify_predictive_edit."
    return True, marker, None


@lifespan
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Initialize configuration on server startup."""
    config = load_config()
    try:
        yield {"config": config}
    finally:
        pass


mcp = FastMCP("rawtherapee", version=__version__, lifespan=app_lifespan)


def get_config(ctx: Context) -> RTConfig:
    """Extract the RTConfig from the MCP context.

    Args:
        ctx: The FastMCP context object.

    Returns:
        The RTConfig instance.

    Raises:
        RuntimeError: If the config is not initialized.
    """
    cfg: Any = ctx.lifespan_context.get("config")
    if not isinstance(cfg, RTConfig):
        msg = "RTConfig not initialized"
        raise RuntimeError(msg)
    return cfg


def _require_rt(config: RTConfig) -> dict[str, Any] | Path:
    """Check that RT CLI is available, returning error dict if not.

    Returns:
        The RT CLI path, or an error dict.
    """
    if config.rt_cli_path is None:
        return {
            "error": "RawTherapee CLI not found",
            "suggestion": "Install RawTherapee and set RT_CLI_PATH, or run check_rt_status for details",
        }
    return config.rt_cli_path


async def _preview_to_image_content(
    preview_path: str,
    max_width: int,
) -> ImageContent:
    """Convert a preview file to a thumbnailed ImageContent.

    Generates a thumbnail from the preview JPEG so it stays within MCP's
    1MB response limit, even when the preview is full-resolution (e.g.
    crop-only profiles where RT can't resize).
    """
    thumb_bytes = await asyncio.to_thread(generate_thumbnail, Path(preview_path), max_width)
    return MCPImage(data=thumb_bytes, format="jpeg").to_image_content()


def _check_crop_resize_conflict(profile: PP3Profile) -> str | None:
    """Return warning string if profile has both Crop and Resize enabled.

    RT 5.12 silently ignores Crop when Resize is also active.
    """
    if profile.get("Crop", "Enabled") == "true" and profile.get("Resize", "Enabled") == "true":
        return (
            "RT 5.12 bug: Crop is ignored when Resize is also enabled. "
            "Disable Resize to preserve the crop, or use preview_raw "
            "which handles this automatically."
        )
    return None


def _check_crop_resize_conflict_text(pp3_text: str) -> str | None:
    """Text-based crop/resize conflict check — no PP3Profile parsing needed."""
    crop_enabled = False
    resize_enabled = False
    current_section = ""
    for line in pp3_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1]
            continue
        if current_section == "Crop" and stripped == "Enabled=true":
            crop_enabled = True
        elif current_section == "Resize" and stripped == "Enabled=true":
            resize_enabled = True
    if crop_enabled and resize_enabled:
        return (
            "RT 5.12 bug: Crop is ignored when Resize is also enabled. "
            "Disable Resize to preserve the crop, or use preview_raw "
            "which handles this automatically."
        )
    return None


def _pp3_text_has_crop(pp3_text: str) -> bool:
    """Check if raw PP3 text has Crop enabled, without full parsing."""
    current_section = ""
    for line in pp3_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1]
            continue
        if current_section == "Crop" and stripped == "Enabled=true":
            return True
    return False


def _pp3_text_set_resize(pp3_text: str, resize_settings: dict[str, str]) -> str:
    """Replace or append [Resize] section in raw PP3 text.

    Overwrites any existing [Resize] section with the given key-value pairs.
    If no [Resize] section exists, appends one at the end.
    """
    lines = pp3_text.splitlines()
    out: list[str] = []
    in_resize = False
    resize_written = False

    for line in lines:
        stripped = line.strip()
        if stripped == "[Resize]":
            in_resize = True
            # Write our replacement section
            out.append("[Resize]")
            for key, value in resize_settings.items():
                out.append(f"{key}={value}")
            resize_written = True
            continue
        if in_resize:
            # Skip old resize lines until the next section header
            if stripped.startswith("[") and stripped.endswith("]"):
                in_resize = False
                out.append(line)
            continue
        out.append(line)

    if not resize_written:
        out.append("")
        out.append("[Resize]")
        for key, value in resize_settings.items():
            out.append(f"{key}={value}")

    return "\n".join(out)


def _summarize_parameter_groups(parameters: dict[str, Any]) -> dict[str, Any]:
    """Return a compact summary of merged parameter groups and keys."""
    groups: list[str] = []
    group_keys: dict[str, list[str]] = {}
    for group_name in sorted(parameters):
        value = parameters[group_name]
        if not isinstance(value, dict):
            continue
        groups.append(group_name)
        group_keys[group_name] = sorted(str(key) for key in value)
    return {"groups": groups, "group_keys": group_keys}


_CROP_RATIO_MAP: dict[str, tuple[int, int] | None] = {
    "original": None,
    "4:5": (4, 5),
    "3:2": (3, 2),
    "1:1": (1, 1),
    "16:9": (16, 9),
}


def _load_profile_or_template(
    profile_name_or_path: str,
    *,
    templates_dir: Path,
    custom_templates_dir: Path,
) -> tuple[PP3Profile, str]:
    """Load a PP3 either from disk or by template name."""
    path = Path(profile_name_or_path)
    if path.is_file():
        profile = PP3Profile()
        profile.load(path)
        return profile, str(path)
    profile = _load_template(profile_name_or_path, templates_dir, custom_templates_dir)
    return profile, profile_name_or_path


def _set_center_crop(
    profile: PP3Profile,
    *,
    source_width: int,
    source_height: int,
    aspect_ratio: str,
    scale: float,
) -> dict[str, Any]:
    """Apply a centered crop with optional aspect-ratio change."""
    ratio_pair = _CROP_RATIO_MAP.get(aspect_ratio)
    if ratio_pair is None:
        crop_w = max(1, int(round(source_width * scale)))
        crop_h = max(1, int(round(source_height * scale)))
        ratio_value = f"{source_width}:{source_height}"
    else:
        target_w, target_h = ratio_pair
        target_ratio = target_w / target_h
        source_ratio = source_width / source_height
        if source_ratio > target_ratio:
            base_h = source_height
            base_w = int(round(base_h * target_ratio))
        else:
            base_w = source_width
            base_h = int(round(base_w / target_ratio))
        crop_w = max(1, int(round(base_w * scale)))
        crop_h = max(1, int(round(base_h * scale)))
        ratio_value = f"{target_w}:{target_h}"

    crop_x = max(0, (source_width - crop_w) // 2)
    crop_y = max(0, (source_height - crop_h) // 2)

    profile.set("Crop", "Enabled", "true")
    profile.set("Crop", "X", str(crop_x))
    profile.set("Crop", "Y", str(crop_y))
    profile.set("Crop", "W", str(crop_w))
    profile.set("Crop", "H", str(crop_h))
    profile.set("Crop", "FixedRatio", "true")
    profile.set("Crop", "Ratio", ratio_value)
    profile.set("Crop", "Orientation", "As Image")
    profile.set("Crop", "Guide", "Frame")
    profile.set("Resize", "Enabled", "false")

    return {
        "x": crop_x,
        "y": crop_y,
        "w": crop_w,
        "h": crop_h,
        "ratio": ratio_value,
        "scale": scale,
    }


def _extract_dimensions_from_image_info(info: dict[str, Any]) -> tuple[int, int]:
    """Return positive width/height from an image-info dict, or ``(0, 0)``."""
    try:
        width = int(info.get("width", 0))
        height = int(info.get("height", 0))
    except (TypeError, ValueError):
        return (0, 0)
    if width <= 0 or height <= 0:
        return (0, 0)
    return (width, height)


async def _resolve_crop_candidate_dimensions(config: RTConfig, raw_path: Path) -> dict[str, Any]:
    """Resolve source dimensions for crop PP3 coordinates with explicit fallbacks."""
    attempts: list[dict[str, Any]] = []

    try:
        image_info = await asyncio.to_thread(_get_image_info, raw_path)
        width, height = _extract_dimensions_from_image_info(image_info)
        attempt = {
            "source": "direct_image_metadata",
            "source_file_used": str(raw_path),
            "success": width > 0 and height > 0,
            "width": width,
            "height": height,
        }
        if "error" in image_info:
            attempt["error"] = image_info["error"]
        attempts.append(attempt)
        if width > 0 and height > 0:
            return {
                "success": True,
                "dimension_source": "direct_image_metadata",
                "source_width": width,
                "source_height": height,
                "source_file_used": str(raw_path),
                "used_preview_fallback": False,
                "dimension_sources_attempted": attempts,
            }
    except Exception as exc:  # noqa: BLE001
        attempts.append(
            {
                "source": "direct_image_metadata",
                "source_file_used": str(raw_path),
                "success": False,
                "error": str(exc),
            }
        )

    try:
        width, height = await asyncio.to_thread(get_effective_dimensions, raw_path)
        attempts.append(
            {
                "source": "effective_exif_dimensions",
                "source_file_used": str(raw_path),
                "success": width > 0 and height > 0,
                "width": width,
                "height": height,
                "error": "" if width > 0 and height > 0 else "No positive EXIF/TIFF dimensions found",
            }
        )
        if width > 0 and height > 0:
            return {
                "success": True,
                "dimension_source": "effective_exif_dimensions",
                "source_width": width,
                "source_height": height,
                "source_file_used": str(raw_path),
                "used_preview_fallback": False,
                "dimension_sources_attempted": attempts,
            }
    except Exception as exc:  # noqa: BLE001
        attempts.append(
            {
                "source": "effective_exif_dimensions",
                "source_file_used": str(raw_path),
                "success": False,
                "error": str(exc),
            }
        )

    if config.rt_cli_path is None:
        attempts.append(
            {
                "source": "rawtherapee_neutral_preview_dimensions",
                "source_file_used": None,
                "success": False,
                "error": "RawTherapee CLI is not configured; cannot generate a preview fallback",
            }
        )
    else:
        timestamp = int(time.time() * 1000)
        probe_profile_path = config.preview_dir / f"_dimension_probe_{timestamp}.pp3"
        preview_path = config.preview_dir / f"_dimension_probe_{raw_path.stem}_{timestamp}.jpg"
        try:
            probe_profile = create_neutral_profile()
            probe_profile.set("Resize", "Enabled", "false")
            probe_profile.set("Crop", "Enabled", "false")
            probe_profile.save(probe_profile_path)

            preview_result = await run_rt_cli(
                rt_path=config.rt_cli_path,
                input_path=raw_path,
                output_path=preview_path,
                profiles=[probe_profile_path],
                output_format="jpeg",
                jpeg_quality=85,
            )
            if preview_result.get("success"):
                preview_info = await asyncio.to_thread(_get_image_info, preview_path)
                width, height = _extract_dimensions_from_image_info(preview_info)
                attempt = {
                    "source": "rawtherapee_neutral_preview_dimensions",
                    "source_file_used": str(preview_path),
                    "success": width > 0 and height > 0,
                    "width": width,
                    "height": height,
                }
                if "error" in preview_info:
                    attempt["error"] = preview_info["error"]
                attempts.append(attempt)
                if width > 0 and height > 0:
                    return {
                        "success": True,
                        "dimension_source": "rawtherapee_neutral_preview_dimensions",
                        "source_width": width,
                        "source_height": height,
                        "source_file_used": str(preview_path),
                        "used_preview_fallback": True,
                        "dimension_sources_attempted": attempts,
                    }
            else:
                attempts.append(
                    {
                        "source": "rawtherapee_neutral_preview_dimensions",
                        "source_file_used": str(preview_path),
                        "success": False,
                        "error": preview_result.get("error", "RawTherapee preview probe did not succeed"),
                        "stderr": preview_result.get("stderr", ""),
                        "stdout": preview_result.get("stdout", ""),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "source": "rawtherapee_neutral_preview_dimensions",
                    "source_file_used": str(preview_path),
                    "success": False,
                    "error": str(exc),
                }
            )
        finally:
            try:
                probe_profile_path.unlink(missing_ok=True)
            except OSError:
                pass

    return {
        "success": False,
        "dimension_source": None,
        "source_width": 0,
        "source_height": 0,
        "source_file_used": None,
        "used_preview_fallback": False,
        "dimension_sources_attempted": attempts,
    }


async def _maybe_attach_thumbnail(
    result: dict[str, Any],
    output_path_key: str = "output_path",
    max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Attach an inline thumbnail to a successful processing result.

    On success, returns ToolResult with TextContent + ImageContent.
    On failure or if the output file is not available, returns the original dict.
    """
    if not result.get("success"):
        return result

    output_path = result.get(output_path_key)
    if not output_path:
        return result

    try:
        thumb_bytes = await asyncio.to_thread(generate_thumbnail, Path(str(output_path)), max_width)
        return ToolResult(
            content=[
                TextContent(type="text", text=json.dumps(result, indent=2)),
                MCPImage(data=thumb_bytes, format="jpeg").to_image_content(),
            ],
            structured_content=result,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Thumbnail generation failed for %s", output_path, exc_info=True)
        return result


async def _render_preview(
    config: RTConfig,
    raw_path: Path,
    profile: PP3Profile | Path,
    max_width: int = 600,
    jpeg_quality: int = 85,
    label: str = "preview",
) -> dict[str, Any]:
    """Render a RAW file with a PP3 profile to a preview JPEG.

    Handles Crop/Resize conflict (RT 5.12 bug), temp PP3 creation, RT CLI
    invocation, and temp file cleanup.

    When ``profile`` is a Path, the PP3 is read as raw text and the Resize
    section is manipulated without full parsing.  This avoids the parser
    crash on profiles with complex Locallab sections.  When ``profile`` is a
    PP3Profile (for in-memory profiles without Locallab), the legacy
    copy-modify-save path is used.

    Args:
        config: Server configuration.
        raw_path: Path to the RAW file.
        profile: PP3 profile to apply — either a PP3Profile object or a
            Path to a ``.pp3`` file on disk.
        max_width: Maximum preview dimension in pixels.
        jpeg_quality: JPEG compression quality (1-100).
        label: Label for temp file naming.

    Returns:
        Dict with ``success``, ``preview_path`` on success, or ``error`` key.
    """
    if config.rt_cli_path is None:
        return {"error": "RawTherapee CLI not found"}

    timestamp = int(time.time() * 1000)
    combined_pp3_path = config.preview_dir / f"_{label}_{timestamp}.pp3"

    if isinstance(profile, Path):
        # --- Raw-text path: bypass PP3Profile parser entirely ---
        pp3_text = profile.read_text(encoding="utf-8")
        has_crop = _pp3_text_has_crop(pp3_text)

        if has_crop:
            resize_settings = {"Enabled": "false"}
        else:
            resize_settings = {
                "Enabled": "true",
                "Scale": "1",
                "AppliesTo": "Full Image",
                "Method": "Lanczos",
                "DataSpecified": "1",
                "Width": str(max_width),
                "Height": str(max_width),
                "AllowUpscaling": "false",
            }

        combined_text = _pp3_text_set_resize(pp3_text, resize_settings)
        combined_pp3_path.write_text(combined_text, encoding="utf-8")
    else:
        # --- PP3Profile path: for in-memory profiles (no Locallab) ---
        combined = profile.copy()

        has_crop = combined.get("Crop", "Enabled") == "true"
        if has_crop:
            combined.set("Resize", "Enabled", "false")
        else:
            combined.set("Resize", "Enabled", "true")
            combined.set("Resize", "Scale", "1")
            combined.set("Resize", "AppliesTo", "Full Image")
            combined.set("Resize", "Method", "Lanczos")
            combined.set("Resize", "DataSpecified", "1")
            combined.set("Resize", "Width", str(max_width))
            combined.set("Resize", "Height", str(max_width))
            combined.set("Resize", "AllowUpscaling", "false")

        combined.save(combined_pp3_path)

    preview_name = f"{label}_{raw_path.stem}_{timestamp}.jpg"
    preview_path = config.preview_dir / preview_name

    result = await run_rt_cli(
        rt_path=config.rt_cli_path,
        input_path=raw_path,
        output_path=preview_path,
        profiles=[combined_pp3_path],
        output_format="jpeg",
        jpeg_quality=jpeg_quality,
    )

    # Include PP3 content in error responses for debugging
    if not result.get("success"):
        try:
            result["preview_pp3_content"] = combined_pp3_path.read_text(encoding="utf-8")
        except OSError:
            pass

    # Clean up temporary profile
    try:
        combined_pp3_path.unlink(missing_ok=True)
    except OSError:
        pass

    if result.get("success"):
        result["preview_path"] = str(preview_path)
        result["max_width"] = max_width

    return result


# ---------------------------------------------------------------------------
# Phase 1 Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def check_rt_status(ctx: Context) -> dict[str, Any]:
    """Check RawTherapee installation status and server configuration.

    Use this to verify RT is installed, check its version, and view the
    configured output directories. Call this first when troubleshooting.
    Returns: dict with installed, cli_path, version, platform, and directory paths.
    """
    config = get_config(ctx)

    result: dict[str, Any] = {
        "installed": config.rt_cli_path is not None,
        "cli_path": str(config.rt_cli_path) if config.rt_cli_path else None,
        "version": None,
        "detection_method": "not_found",
        "platform": platform.system(),
        "output_dir": str(config.output_dir),
        "preview_dir": str(config.preview_dir),
        "custom_templates_dir": str(config.custom_templates_dir),
        "preview_max_width": config.preview_max_width,
        "default_jpeg_quality": config.default_jpeg_quality,
        "mcp_version": __version__,
    }

    if config.rt_cli_path:
        import os

        if os.environ.get("RT_CLI_PATH"):
            result["detection_method"] = "env_var"
        else:
            result["detection_method"] = "auto_detected"

        version = await get_rt_version(config.rt_cli_path)
        result["version"] = version

    return result


@mcp.tool()
async def list_raw_files(
    ctx: Context,
    directory: str,
    recursive: bool = False,
) -> dict[str, Any]:
    """Scan a directory for supported RAW image files.

    Use this to discover which RAW files are available for processing.
    Returns: dict with files list (path, size, extension) and count.
    Params: directory, recursive (default: false)
    """
    dir_path = Path(directory)

    if not dir_path.is_dir():
        return {"error": f"Directory not found: {directory}"}

    found_files: list[dict[str, Any]] = []
    pattern = "**/*" if recursive else "*"

    for file_path in sorted(dir_path.glob(pattern)):
        if file_path.is_file() and file_path.suffix.lower() in RAW_EXTENSIONS:
            found_files.append(
                {
                    "path": str(file_path),
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "extension": file_path.suffix.lower(),
                }
            )

    return {"files": found_files, "count": len(found_files), "directory": str(dir_path)}


@mcp.tool()
async def infer_photo_intent(
    ctx: Context,
    file_path: str,
    user_intent: str | None = None,
    context_hint: str | None = None,
) -> dict[str, Any]:
    """Build a structured intent-inference contract before editorial editing.

    This tool does not perform computer vision. The LLM must inspect preview
    output and fill this contract honestly. If the image was not previewed yet,
    run preview_raw first.
    Params: file_path, user_intent, context_hint
    """
    _ = get_config(ctx)
    try:
        raw_path = ensure_existing_file(file_path)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    return build_intent_inference_contract(
        str(raw_path),
        user_intent=user_intent,
        context_hint=context_hint,
    )


@mcp.tool()
async def create_editing_vision(
    ctx: Context,
    file_path: str,
    user_intent: str | None = None,
    context_hint: str | None = None,
) -> dict[str, Any]:
    """Build a structured editing-vision contract before generating candidates.

    This tool does not perform computer vision. The LLM must inspect preview
    output and fill the contract honestly after looking at the image.
    Params: file_path, user_intent, context_hint
    """
    _ = get_config(ctx)
    try:
        raw_path = ensure_existing_file(file_path)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    return build_editing_vision_contract(
        str(raw_path),
        user_intent=user_intent,
        context_hint=context_hint,
    )


@mcp.tool()
async def create_composition_plan(
    ctx: Context,
    file_path: str,
    editing_vision: dict[str, Any],
    aspect_ratio: str = "original",
) -> dict[str, Any]:
    """Build a structured composition/crop planning contract before crop testing.

    This tool does not perform computer vision. It translates the editing
    vision into composition questions and crop priorities that should be
    checked visually in previews.
    Params: file_path, editing_vision, aspect_ratio
    """
    _ = get_config(ctx)
    try:
        raw_path = ensure_existing_file(file_path)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    validation_error = validate_filled_editing_vision(editing_vision)
    if validation_error:
        return {"error": validation_error}

    return build_composition_plan(
        str(raw_path),
        editing_vision,
        aspect_ratio=aspect_ratio,
    )


@mcp.tool()
async def generate_crop_candidates(
    ctx: Context,
    file_path: str,
    base_name: str,
    editing_vision: dict[str, Any],
    base_profile: str | None = None,
) -> dict[str, Any]:
    """Generate safe crop-only PP3 variants for preview and hierarchy testing.

    Creates conservative crop profile variants from an existing candidate or
    neutral baseline. This tool never exports and should be followed by
    preview_raw/critique_gate before any decision.
    Params: file_path, base_name, editing_vision, base_profile
    """
    config = get_config(ctx)
    templates_dir = _get_templates_dir()

    try:
        raw_path = ensure_existing_file(file_path)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    validation_error = validate_filled_editing_vision(editing_vision)
    if validation_error:
        return {"error": validation_error}

    dimension_result = await _resolve_crop_candidate_dimensions(config, raw_path)
    source_width = int(dimension_result["source_width"])
    source_height = int(dimension_result["source_height"])
    if source_width <= 0 or source_height <= 0:
        return {
            "error": f"Could not determine effective dimensions for {file_path}",
            "dimension_source": dimension_result["dimension_source"],
            "source_width": source_width,
            "source_height": source_height,
            "source_file_used": dimension_result["source_file_used"],
            "used_preview_fallback": dimension_result["used_preview_fallback"],
            "dimension_sources_attempted": dimension_result["dimension_sources_attempted"],
            "suggestion": (
                "Provide a RAW file with readable EXIF dimensions, configure RawTherapee CLI so a neutral "
                "preview probe can be generated, or run preview_raw first and check that RawTherapee can decode "
                "the file."
            ),
        }

    base_profile_name = base_profile or "neutral"
    try:
        base, resolved_base_profile = _load_profile_or_template(
            base_profile_name,
            templates_dir=templates_dir,
            custom_templates_dir=config.custom_templates_dir,
        )
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    candidates: list[dict[str, Any]] = []
    for spec in build_crop_candidate_specs(editing_vision):
        candidate_name = str(spec["candidate_name"])
        candidate_slug = safe_slug(f"{base_name}_{candidate_name}")
        profile = base.copy()
        aspect_ratio = str(spec["aspect_ratio"])
        scale = 0.92 if candidate_name == "original_aspect_tighten" else 0.96
        if candidate_name == "4x5_travel_vertical":
            scale = 0.94

        crop_window = _set_center_crop(
            profile,
            source_width=source_width,
            source_height=source_height,
            aspect_ratio=aspect_ratio,
            scale=scale,
        )
        output_path = config.custom_templates_dir / f"{candidate_slug}.pp3"
        profile.save(output_path)

        candidates.append(
            {
                **spec,
                "candidate_name": candidate_name,
                "profile_path": str(output_path),
                "base_profile": resolved_base_profile,
                "aspect_ratio": aspect_ratio,
                "crop_coordinates": {
                    "x": crop_window["x"],
                    "y": crop_window["y"],
                    "width": crop_window["w"],
                    "height": crop_window["h"],
                },
                "crop_width": crop_window["w"],
                "crop_height": crop_window["h"],
                "crop_x": crop_window["x"],
                "crop_y": crop_window["y"],
                "crop_window": crop_window,
                "composition_improvement_needed": True,
                "crop_or_geometry_suggested": True,
                "preview_required": True,
                "export_allowed_without_preview": False,
            }
        )

    return {
        "file_path": str(raw_path),
        "base_name": base_name,
        "base_profile": resolved_base_profile,
        "editing_vision": editing_vision,
        "dimension_source": dimension_result["dimension_source"],
        "source_width": source_width,
        "source_height": source_height,
        "source_file_used": dimension_result["source_file_used"],
        "used_preview_fallback": dimension_result["used_preview_fallback"],
        "dimension_sources_attempted": dimension_result["dimension_sources_attempted"],
        "source_dimensions": {"width": source_width, "height": source_height},
        "candidates": candidates,
        "workflow_reminder": (
            "Preview each crop candidate before choosing. Crop alone is not an export decision; "
            "run critique_gate after preview and only continue if hierarchy clearly improves."
        ),
    }


@mcp.tool()
async def list_visual_editing_moves(ctx: Context) -> dict[str, Any]:
    """Return the compact palette of safe vision-first editing moves.

    Use this when planning edits in artistic language before translating them
    into safe PP3 adjustments.
    """
    _ = get_config(ctx)
    return build_visual_move_list()


@mcp.tool()
async def visual_moves_to_parameters(
    ctx: Context,
    moves: list[str],
    intensity: str = "medium",
    intent_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Translate visual moves into sanitized autonomous parameter dictionaries.

    This wrapper keeps output JSON-serializable and includes safety/debug fields.
    """
    _ = get_config(ctx)
    parameter_plan = map_visual_moves_to_parameter_plan(
        moves,
        intensity=intensity,
        intent_profile=intent_profile,
    )
    sanitized_parameters, sanitization_notes = sanitize_autonomous_parameters(parameter_plan["parameters"])
    return {
        "moves": list(moves),
        "intensity": intensity,
        "intent_profile": intent_profile,
        "moves_requested": parameter_plan["moves_requested"],
        "visual_moves_used": parameter_plan["visual_moves_used"],
        "visual_moves_blocked": parameter_plan["visual_moves_blocked"],
        "techniques_used": parameter_plan["techniques_used"],
        "techniques_blocked": parameter_plan["techniques_blocked"],
        "unknown_techniques": parameter_plan["unknown_techniques"],
        "overwritten_parameters": parameter_plan["overwritten_parameters"],
        "merge_conflicts": parameter_plan["overwritten_parameters"],
        "blocked_risk_tags": parameter_plan["blocked_risk_tags"],
        "parameters": sanitized_parameters,
        "safety_sanitizations_applied": sanitization_notes,
    }


@mcp.tool()
async def create_editorial_brief(
    ctx: Context,
    file_path: str,
    intent: str | None = None,
    inferred_intent: dict[str, Any] | None = None,
    intent_profile: dict[str, Any] | None = None,
    editing_vision: dict[str, Any] | None = None,
    style: str = "clean_editorial",
    output_goal: str = "post_worthy",
) -> dict[str, Any]:
    """Create a strict, opinionated editing brief for autonomous RAW refinement.

    This is a planning and discipline tool, not an export tool. Use it to force
    a critique/refine/reject workflow before process_raw is called.
    Params: file_path, intent, style, output_goal
    """
    path = Path(file_path)
    if not path.is_file():
        return {"error": f"File not found: {file_path}"}

    exif = read_exif_data(path)
    metadata: dict[str, Any] = {"effective_dimensions": get_effective_dimensions(path)}
    if "error" not in exif:
        metadata["exif"] = exif
        metadata["recommendations"] = generate_recommendations(exif)

    resolved_intent_profile = intent_profile if intent_profile is not None else inferred_intent

    return build_editorial_brief(
        str(path),
        intent=intent,
        style=style,
        output_goal=output_goal,
        inferred_intent=resolved_intent_profile,
        editing_vision=editing_vision,
        metadata=metadata,
    )


@mcp.tool()
async def generate_editorial_candidates(
    ctx: Context,
    file_path: str,
    base_name: str,
    style_family: str = "travel_portrait",
    device_preset: str | None = None,
    inferred_intent: dict[str, Any] | None = None,
    style_direction: str | None = None,
    editing_vision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """DO NOT USE FOR AUTONOMOUS EDITING. DO NOT USE FOR FINAL EXPORT.

    Creates clean_editorial, warm_travel, and cinematic_soft profiles with
    stronger visible differences. Do not use for autonomous final edits.
    Use auto_edit_manifest_select_prepare + verify_predictive_edit instead.
    Params: file_path, base_name, style_family, device_preset
    """
    config = get_config(ctx)
    templates_dir = _get_templates_dir()

    try:
        raw_path = ensure_existing_file(file_path)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    preset_dict: dict[str, Any] | None = None
    if device_preset:
        preset_dict = get_preset(device_preset, config.custom_templates_dir)
        if preset_dict is None:
            return {"error": f"Device preset '{device_preset}' not found"}

    source_dimensions: tuple[int, int] = get_effective_dimensions(raw_path)
    candidate_styles = ("clean_editorial", "warm_travel", "cinematic_soft")
    candidates: list[dict[str, Any]] = []
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check
    rt_version = await get_rt_version(rt_check)

    for style_name in candidate_styles:
        candidate_slug = safe_slug(f"{base_name}_{style_name}")
        parameters = editorial_candidate_parameters(
            style_name,
            style_family,
            inferred_intent=inferred_intent,
            style_direction=style_direction,
            rt_version=rt_version,
        )
        if editing_vision:
            visual_parameters = map_visual_moves_to_parameters(
                resolve_visual_moves(editing_vision),
                intensity="medium",
                intent_profile=inferred_intent or editing_vision,
            )
            parameters = merge_parameter_sets(parameters, visual_parameters)
        sanitized_parameters, sanitization_notes = sanitize_autonomous_parameters(parameters)

        try:
            profile, output_path = _generate_profile(
                name=candidate_slug,
                base_template="neutral",
                parameters=sanitized_parameters,
                device_preset=preset_dict,
                templates_dir=templates_dir,
                custom_templates_dir=config.custom_templates_dir,
            )
        except FileNotFoundError as exc:
            return {"error": str(exc)}

        if preset_dict:
            src_w, src_h = source_dimensions
            if src_w > 0 and src_h > 0:
                apply_device_crop(profile, preset_dict, src_w, src_h)
                profile.save(output_path)

        descriptor = build_candidate_descriptor(style_name)
        descriptor["profile_path"] = str(output_path)
        descriptor["safety_sanitizations_applied"] = sanitization_notes
        candidates.append(descriptor)

    return {
        "file_path": str(raw_path),
        "base_name": base_name,
        "style_family": style_family,
        "device_preset": device_preset,
        "inferred_intent": inferred_intent,
        "style_direction": style_direction,
        "editing_vision": editing_vision,
        "candidates": candidates,
        "workflow_reminder": (
            "Legacy/debug/manual-only path. Preview every candidate, then use "
            "auto_edit_manifest_select_prepare + verify_predictive_edit for autonomous final decisions."
        ),
        "legacy_status": "legacy_debug_manual_only",
        "verification_required_before_export": True,
        "recommended_next_tool": "verify_predictive_edit",
        "recommended_prepare_tool": "auto_edit_manifest_select_prepare",
    }


@mcp.tool()
async def generate_vision_candidates(
    ctx: Context,
    file_path: str,
    base_name: str,
    editing_vision: dict[str, Any],
    intensity: str = "medium",
    device_preset: str | None = None,
) -> dict[str, Any]:
    """DO NOT USE FOR AUTONOMOUS EDITING. DO NOT USE FOR FINAL EXPORT.

    Creates faithful_refinement, expressive_refinement, and restrained_experiment
    profiles from the editing vision instead of fixed style presets.
    Legacy path: deprecated for autonomous default use.
    Params: file_path, base_name, editing_vision, intensity, device_preset
    """
    config = get_config(ctx)
    templates_dir = _get_templates_dir()

    try:
        raw_path = ensure_existing_file(file_path)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    preset_dict: dict[str, Any] | None = None
    if device_preset:
        preset_dict = get_preset(device_preset, config.custom_templates_dir)
        if preset_dict is None:
            return {"error": f"Device preset '{device_preset}' not found"}

    source_dimensions = get_effective_dimensions(raw_path)
    validation_error = validate_filled_editing_vision(editing_vision)
    if validation_error:
        return {"error": validation_error}
    candidate_specs = build_vision_candidate_specs(editing_vision, intensity=intensity)
    candidates: list[dict[str, Any]] = []

    for candidate_spec in candidate_specs:
        candidate_name = str(candidate_spec["candidate_name"])
        candidate_slug = safe_slug(f"{base_name}_{candidate_name}")
        visual_moves_requested = list(candidate_spec["visual_moves_used"])
        parameter_plan = map_visual_moves_to_parameter_plan(
            visual_moves_requested,
            intensity=str(candidate_spec["parameter_intensity"]),
            intent_profile=editing_vision,
        )
        sanitized_parameters, sanitization_notes = sanitize_autonomous_parameters(parameter_plan["parameters"])

        try:
            profile, output_path = _generate_profile(
                name=candidate_slug,
                base_template="neutral",
                parameters=sanitized_parameters,
                device_preset=preset_dict,
                templates_dir=templates_dir,
                custom_templates_dir=config.custom_templates_dir,
            )
        except FileNotFoundError as exc:
            return {"error": str(exc)}

        if preset_dict:
            src_w, src_h = source_dimensions
            if src_w > 0 and src_h > 0:
                apply_device_crop(profile, preset_dict, src_w, src_h)
                profile.save(output_path)

        descriptor = dict(candidate_spec)
        descriptor["moves_requested"] = parameter_plan["moves_requested"]
        descriptor["visual_moves_used"] = parameter_plan["visual_moves_used"]
        descriptor["visual_moves_blocked"] = parameter_plan["visual_moves_blocked"]
        descriptor["techniques_used"] = parameter_plan["techniques_used"]
        descriptor["techniques_blocked"] = parameter_plan["techniques_blocked"]
        descriptor["unknown_techniques"] = parameter_plan["unknown_techniques"]
        descriptor["overwritten_parameters"] = parameter_plan["overwritten_parameters"]
        descriptor["blocked_risk_tags"] = parameter_plan["blocked_risk_tags"]
        descriptor["merged_parameter_summary"] = _summarize_parameter_groups(parameter_plan["parameters"])
        descriptor["profile_path"] = str(output_path)
        descriptor["safety_sanitizations_applied"] = sanitization_notes
        candidates.append(descriptor)

    return {
        "file_path": str(raw_path),
        "base_name": base_name,
        "intensity": intensity,
        "device_preset": device_preset,
        "editing_vision": editing_vision,
        "legacy_status": "deprecated for autonomous default use",
        "deprecated_reason": (
            "Use auto_edit_manifest_select_prepare + verify_predictive_edit as the default autonomous path; "
            "generate_vision_candidates remains for legacy comparison/debug/manual work."
        ),
        "candidates": candidates,
        "workflow_reminder": (
            "Legacy/debug/manual-only path. Do not export directly from these candidates. "
            "Use auto_edit_manifest_select_prepare + verify_predictive_edit for autonomous final edits."
        ),
        "verification_required_before_export": True,
        "recommended_next_tool": "verify_predictive_edit",
        "recommended_prepare_tool": "auto_edit_manifest_select_prepare",
    }


@mcp.tool()
async def legacy_generate_vision_candidates(
    ctx: Context,
    file_path: str,
    base_name: str,
    editing_vision: dict[str, Any],
    intensity: str = "medium",
    device_preset: str | None = None,
) -> dict[str, Any]:
    """DO NOT USE FOR AUTONOMOUS EDITING. DO NOT USE FOR FINAL EXPORT.

    This exposes the old autonomous candidate flow explicitly for debug and
    A/B comparison. Default autonomous editing should use
    auto_edit_manifest_select_prepare + verify_predictive_edit.
    """
    result = await generate_vision_candidates(
        ctx,
        file_path=file_path,
        base_name=base_name,
        editing_vision=editing_vision,
        intensity=intensity,
        device_preset=device_preset,
    )
    if "error" not in result:
        result["legacy_tool"] = True
        result["verification_required_before_export"] = True
        result["recommended_next_tool"] = "verify_predictive_edit"
        result["recommended_prepare_tool"] = "auto_edit_manifest_select_prepare"
    return result


def _should_allow_predictive_export(
    *,
    validation_allowed: bool,
    global_visible_difference_score: float,
    subject_hierarchy_score: float,
    thumbnail_subject_read_score: float,
    color_quality_score: float,
    naturalness_score: float,
    artifact_free_score: float,
    crop_dependency: str,
) -> bool:
    """Export gate for predictive edits."""
    return bool(
        score_predictive_export_decision(
            validation_allowed=validation_allowed,
            global_visible_difference_score=global_visible_difference_score,
            subject_hierarchy_score=subject_hierarchy_score,
            thumbnail_subject_read_score=thumbnail_subject_read_score,
            color_quality_score=color_quality_score,
            naturalness_score=naturalness_score,
            artifact_free_score=artifact_free_score,
            crop_dependency=crop_dependency,
        )["export_gate_passed"]
    )


def _predictive_export_decision(validation_allowed: bool, scores: dict[str, Any]) -> dict[str, Any]:
    """Normalize predictive scores and compute the export/proof decision."""
    global_visible_difference_score = float(
        scores.get("global_visible_difference_score", scores.get("visible_difference_score", 0.0))
    )
    global_pixel_difference = float(scores.get("global_pixel_difference", global_visible_difference_score))
    subject_hierarchy_score = float(
        scores.get("subject_hierarchy_score", scores.get("hierarchy_improvement_score", 0.0))
    )
    thumbnail_subject_read_score = float(
        scores.get("thumbnail_subject_read_score", scores.get("hierarchy_improvement_score", 0.0))
    )
    color_quality_score = float(scores.get("color_quality_score", 0.0))
    naturalness_score = float(scores.get("naturalness_score", 0.0))
    artifact_free_score = float(
        scores.get(
            "artifact_free_score",
            9.0 if str(scores.get("artifact_check", "")) == "pass" else 0.0,
        )
    )
    crop_dependency = str(scores.get("crop_dependency", "unknown"))
    decision = score_predictive_export_decision(
        validation_allowed=validation_allowed,
        global_visible_difference_score=global_visible_difference_score,
        subject_hierarchy_score=subject_hierarchy_score,
        thumbnail_subject_read_score=thumbnail_subject_read_score,
        color_quality_score=color_quality_score,
        naturalness_score=naturalness_score,
        artifact_free_score=artifact_free_score,
        crop_dependency=crop_dependency,
        global_pixel_difference=global_pixel_difference,
        non_crop_tonal_improvement=float(scores.get("non_crop_tonal_improvement", 0.0)),
        subject_separation_improvement=float(scores.get("subject_separation_improvement", 0.0)),
        color_intent_improvement=float(scores.get("color_intent_improvement", 0.0)),
        highlight_shadow_quality=float(scores.get("highlight_shadow_quality", 0.0)),
        composition_improvement=float(scores.get("composition_improvement", 0.0)),
        crop_contribution=float(scores.get("crop_contribution", 0.0)),
        perceived_non_crop_improvement=(
            str(scores["perceived_non_crop_improvement"])
            if "perceived_non_crop_improvement" in scores
            else None
        ),
    )
    return {
        "global_visible_difference_score": global_visible_difference_score,
        "global_pixel_difference": global_pixel_difference,
        "subject_hierarchy_score": subject_hierarchy_score,
        "thumbnail_subject_read_score": thumbnail_subject_read_score,
        "color_quality_score": color_quality_score,
        "naturalness_score": naturalness_score,
        "artifact_free_score": artifact_free_score,
        "crop_dependency": crop_dependency,
        "non_crop_tonal_improvement": float(scores.get("non_crop_tonal_improvement", 0.0)),
        "subject_separation_improvement": float(scores.get("subject_separation_improvement", 0.0)),
        "color_intent_improvement": float(scores.get("color_intent_improvement", 0.0)),
        "highlight_shadow_quality": float(scores.get("highlight_shadow_quality", 0.0)),
        "composition_improvement": float(scores.get("composition_improvement", 0.0)),
        "crop_contribution": float(scores.get("crop_contribution", 0.0)),
        "perceived_non_crop_improvement": decision["perceived_non_crop_improvement"],
        "meaningful_non_crop_edit": decision["meaningful_non_crop_edit"],
        "non_crop_quality_pass_count": decision["non_crop_quality_pass_count"],
        "non_crop_quality_pass_fields": decision["non_crop_quality_pass_fields"],
        "crop_only_improvement": decision["crop_only_improvement"],
        "non_crop_edit_quality": decision["non_crop_edit_quality"],
        "non_crop_edit_quality_reason": decision["non_crop_edit_quality_reason"],
        "hierarchy_boost_applied": bool(scores.get("hierarchy_boost_applied", False)),
        "artifact_check": "pass" if artifact_free_score >= 8.0 else "fail",
        "decision": decision["decision"],
        "export_gate_passed": decision["export_gate_passed"],
        "gate_requirements": decision["gate_requirements"],
        "scoring_guidance": decision["scoring_guidance"],
        "visible_difference_score": global_visible_difference_score,
        "hierarchy_improvement_score": subject_hierarchy_score,
    }


_VERIFY_DESCRIPTION_FIELDS = (
    "subject_change_description",
    "midtone_change_description",
    "highlight_shadow_description",
    "color_change_description",
    "artifact_description",
    "crop_dependency_description",
)

_VERIFY_SCORE_FIELDS = (
    "subject_separation_improvement",
    "non_crop_tonal_improvement",
    "color_intent_improvement",
    "highlight_shadow_quality",
    "composition_improvement",
    "crop_contribution",
    "perceived_non_crop_improvement",
    "artifact_check",
    "naturalness_score",
    "artifact_free_score",
)

_NEGATIVE_ARTIFACT_TERMS = (
    "harsh",
    "crunchy",
    "halo",
    "halos",
    "posterized",
    "unnatural",
    "oversharpened",
    "muddy",
    "blown",
    "clipped",
    "noisy",
    "grainy",
    "cyan split",
    "orange split",
    "fake hdr",
    "color cast",
    "green cast",
    "cyan cast",
    "flat",
    "washed",
    "milky",
    "lifted blacks",
    "crushed",
    "banding",
)


def _verification_packet(subject: str) -> dict[str, Any]:
    return {
        "subject": subject,
        "questions": [
            "Describe what changed around the main subject.",
            "Describe whether the subject separates more clearly from the background.",
            "Describe what changed in midtones.",
            "Describe what changed in highlights/shadows.",
            "Describe what changed in color.",
            "Describe any artifacts or unnatural effects.",
            "Is the visible improvement mostly crop/framing or tonal/color/detail?",
        ],
        "required_descriptions": list(_VERIFY_DESCRIPTION_FIELDS),
        "score_fields_required": list(_VERIFY_SCORE_FIELDS),
    }


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _build_before_after_preview(
    *,
    base_preview_path: str | None,
    edited_preview_path: str | None,
    output_path: Path,
) -> str | None:
    if not base_preview_path or not edited_preview_path:
        return None
    before = Path(base_preview_path)
    after = Path(edited_preview_path)
    if not before.is_file() or not after.is_file():
        return None
    with PILImage.open(before) as before_img, PILImage.open(after) as after_img:
        height = max(before_img.height, after_img.height)
        width = before_img.width + after_img.width
        canvas = PILImage.new("RGB", (width, height), color="black")
        canvas.paste(before_img.convert("RGB"), (0, 0))
        canvas.paste(after_img.convert("RGB"), (before_img.width, 0))
        canvas.save(output_path, "JPEG")
    return str(output_path)


async def _tool_result_with_preview_images(
    payload: dict[str, Any],
    *,
    max_width: int,
    image_paths: list[str | None],
) -> dict[str, Any] | ToolResult:
    content: list[Any] = [TextContent(type="text", text=json.dumps(payload, indent=2))]
    for path in image_paths:
        if not path:
            continue
        file_path = Path(path)
        if not file_path.is_file():
            continue
        try:
            content.append(await _preview_to_image_content(str(file_path), max_width))
        except Exception:  # noqa: BLE001
            logger.debug("Failed to attach inline preview image: %s", file_path, exc_info=True)
    if len(content) == 1:
        return payload
    return ToolResult(content=content, structured_content=payload)


async def _prepare_manifest_select_packet(
    ctx: Context,
    *,
    raw_path: str,
    edit_plan: dict[str, Any],
    preview_width: int,
) -> dict[str, Any]:
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    try:
        source_raw = ensure_existing_file(raw_path)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    translated = build_manifest_select_edit_plan(edit_plan)
    if translated.get("status") == "edit_plan_invalid":
        return {
            "status": "edit_plan_invalid",
            "decision": "verification_required_not_reached",
            "missing_fields": translated.get("missing_fields", []),
        }

    if translated.get("status") == "control_selection_invalid":
        return {
            "status": "control_selection_invalid",
            "decision": "verification_required_not_reached",
            "raw_path": str(source_raw),
            "image_observation": translated.get("image_observation", {}),
            "vision_interpretation": translated.get("vision_interpretation", {}),
            "control_selections": translated.get("control_selections", []),
            "controls_considered_but_rejected": translated.get("controls_considered_but_rejected", []),
            "non_goals": translated.get("non_goals", []),
            "blocked": translated.get("blocked", []),
            "validation": translated.get("validation", {}),
        }

    parameters = translated.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}

    profile_name = safe_slug(f"{source_raw.stem}_manifest_select")
    templates_dir = _get_templates_dir()
    try:
        _profile, profile_path = _generate_profile(
            name=profile_name,
            base_template="neutral",
            parameters=parameters,
            device_preset=None,
            templates_dir=templates_dir,
            custom_templates_dir=config.custom_templates_dir,
        )
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    edited_preview_result = await _render_preview(
        config,
        source_raw,
        Path(profile_path),
        max_width=preview_width,
        label="manifest_select",
    )
    if not edited_preview_result.get("success"):
        return {
            "error": "Failed to render manifest-select preview",
            "details": edited_preview_result,
            "profile_path": str(profile_path),
            "parameters": parameters,
            "validation": translated.get("validation", {}),
        }

    base_preview_result = await _render_preview(
        config,
        source_raw,
        PP3Profile(),
        max_width=preview_width,
        label="manifest_select_base",
    )
    if not base_preview_result.get("success"):
        return {
            "error": "Failed to render base preview",
            "details": base_preview_result,
            "profile_path": str(profile_path),
            "parameters": parameters,
            "validation": translated.get("validation", {}),
        }

    before_after_name = f"manifest_select_compare_{source_raw.stem}_{int(time.time() * 1000)}.jpg"
    before_after_path = _build_before_after_preview(
        base_preview_path=base_preview_result.get("preview_path"),
        edited_preview_path=edited_preview_result.get("preview_path"),
        output_path=config.preview_dir / before_after_name,
    )

    return {
        "status": "verification_required",
        "decision": "verification_required",
        "decision_source": "auto_edit_manifest_select_prepare",
        "prepare_mode": "manifest_select",
        "raw_path": str(source_raw),
        "profile_path": str(profile_path),
        "base_preview_path": base_preview_result.get("preview_path"),
        "edited_preview_path": edited_preview_result.get("preview_path"),
        "preview_path": edited_preview_result.get("preview_path"),
        "before_after_path": before_after_path,
        "image_observation": translated.get("image_observation", {}),
        "vision_interpretation": translated.get("vision_interpretation", {}),
        "control_selections": translated.get("control_selections", []),
        "controls_considered_but_rejected": translated.get("controls_considered_but_rejected", []),
        "non_goals": translated.get("non_goals", []),
        "parameters": parameters,
        "validation": translated.get("validation", {}),
        "verification_packet": _verification_packet(str(translated.get("image_observation", {}).get("main_subject", "primary subject"))),
    }


def _normalize_verification_observed_scores(
    raw_scores: dict[str, Any],
    *,
    crop_dependency: str,
) -> dict[str, Any]:
    perceived = str(raw_scores.get("perceived_non_crop_improvement", "none")).strip().lower()
    if perceived not in {"none", "weak", "moderate", "strong"}:
        perceived = "none"
    artifact_check = str(raw_scores.get("artifact_check", "pass")).strip().lower()
    if artifact_check not in {"pass", "fail"}:
        artifact_check = "pass"
    return {
        "global_pixel_difference": _coerce_float(raw_scores.get("global_pixel_difference"), 0.0),
        "non_crop_tonal_improvement": _coerce_float(raw_scores.get("non_crop_tonal_improvement"), 0.0),
        "subject_separation_improvement": _coerce_float(raw_scores.get("subject_separation_improvement"), 0.0),
        "color_intent_improvement": _coerce_float(raw_scores.get("color_intent_improvement"), 0.0),
        "highlight_shadow_quality": _coerce_float(raw_scores.get("highlight_shadow_quality"), 0.0),
        "composition_improvement": _coerce_float(raw_scores.get("composition_improvement"), 0.0),
        "crop_contribution": _coerce_float(raw_scores.get("crop_contribution"), 0.0),
        "perceived_non_crop_improvement": perceived,
        "artifact_check": artifact_check,
        "artifact_free_score": _coerce_float(
            raw_scores.get("artifact_free_score"),
            9.0 if artifact_check == "pass" else 0.0,
        ),
        "naturalness_score": _coerce_float(
            raw_scores.get("naturalness_score"),
            8.0 if artifact_check == "pass" else 0.0,
        ),
        "subject_hierarchy_score": _coerce_float(
            raw_scores.get("subject_hierarchy_score", raw_scores.get("subject_separation_improvement")),
            _coerce_float(raw_scores.get("subject_separation_improvement"), 0.0),
        ),
        "thumbnail_subject_read_score": _coerce_float(
            raw_scores.get("thumbnail_subject_read_score", raw_scores.get("subject_separation_improvement")),
            _coerce_float(raw_scores.get("subject_separation_improvement"), 0.0),
        ),
        "color_quality_score": _coerce_float(
            raw_scores.get("color_quality_score", raw_scores.get("color_intent_improvement")),
            _coerce_float(raw_scores.get("color_intent_improvement"), 0.0),
        ),
        "crop_dependency": crop_dependency,
    }


def _verify_required_descriptions(verification_observations: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in _VERIFY_DESCRIPTION_FIELDS:
        value = verification_observations.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    return missing


def _consistency_checks(
    verification_observations: dict[str, Any],
    visual_scores: dict[str, Any],
) -> dict[str, Any]:
    text_parts = [
        str(verification_observations.get(field, "")).lower()
        for field in (
            "subject_change_description",
            "background_change_description",
            "midtone_change_description",
            "highlight_shadow_description",
            "color_change_description",
            "artifact_description",
            "crop_dependency_description",
        )
    ]
    combined = " ".join(text_parts)
    warnings: list[dict[str, Any]] = []
    if any(term in combined for term in _NEGATIVE_ARTIFACT_TERMS):
        flagged_values = (
            ("artifact_free_score", _coerce_float(visual_scores.get("artifact_free_score"), 0.0), 7.0),
            ("naturalness_score", _coerce_float(visual_scores.get("naturalness_score"), 0.0), 7.0),
            ("highlight_shadow_quality", _coerce_float(visual_scores.get("highlight_shadow_quality"), 0.0), 7.0),
        )
        for field, score, threshold in flagged_values:
            if score > threshold:
                warnings.append(
                    {
                        "field": field,
                        "reason": (
                            "Descriptions mention potential artifacts/unnatural traits "
                            f"but {field} is {score:.1f}"
                        ),
                    }
                )
        if str(visual_scores.get("artifact_check", "pass")) == "pass":
            warnings.append(
                {
                    "field": "artifact_check",
                    "reason": "Descriptions mention artifact-like terms but artifact_check is pass",
                }
            )
    return {"warnings": warnings, "score_adjustments": []}


def _has_explicit_verification_scores(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    possible_scored_payloads = [payload]
    nested = payload.get("before_after_judgment")
    if isinstance(nested, dict):
        possible_scored_payloads.append(nested)
    nested_scores = payload.get("visual_verification_scores")
    if isinstance(nested_scores, dict):
        possible_scored_payloads.append(nested_scores)
    return any(any(field in candidate for field in _VERIFY_SCORE_FIELDS) for candidate in possible_scored_payloads)


async def _prepare_predictive_packet(
    ctx: Context,
    *,
    raw_path: str,
    style: str,
    intensity: str,
    user_brief: str | None,
    preview_width: int,
    diagnosis_override: dict[str, Any] | None,
) -> dict[str, Any]:
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    try:
        source_raw = ensure_existing_file(raw_path)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    plan = build_predictive_edit_plan(
        style=style,
        intensity=intensity,
        user_brief=user_brief,
        diagnosis_payload=diagnosis_override,
    )
    parameters = plan["parameters"]
    validation = validate_autonomous_parameters(parameters)
    validation_blocked = [
        {
            "control_id": item.control_id,
            "section": item.section,
            "key": item.key,
            "value": item.value,
            "reason": item.reason,
        }
        for item in validation.blocked_controls
    ]

    if not validation.allowed:
        return {
            "status": "validation_failed",
            "decision": "validation_failed",
            "raw_path": str(source_raw),
            "style": style,
            "intensity": intensity,
            "diagnosis": plan["diagnosis"],
            "parameters": parameters,
            "expected_effects": plan["expected_effect"],
            "validation": {"allowed": False, "blocked": validation_blocked, "clamped": plan["clamped"]},
            "blocked_controls_considered": plan["blocked_controls_considered"],
            "approved_curves_used": plan.get("approved_curves_used", []),
            "verification_packet": _verification_packet("primary subject"),
            "reason": "Manifest validation failed; verification/export path is blocked.",
        }

    profile_name = safe_slug(f"{source_raw.stem}_predictive_{style}_{intensity}")
    templates_dir = _get_templates_dir()
    try:
        _profile, profile_path = _generate_profile(
            name=profile_name,
            base_template="neutral",
            parameters=parameters,
            device_preset=None,
            templates_dir=templates_dir,
            custom_templates_dir=config.custom_templates_dir,
        )
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    edited_preview_result = await _render_preview(
        config,
        source_raw,
        Path(profile_path),
        max_width=preview_width,
        label="predictive",
    )
    if not edited_preview_result.get("success"):
        return {
            "error": "Failed to render predictive preview",
            "details": edited_preview_result,
            "profile_path": str(profile_path),
            "parameters": parameters,
            "validation": {"allowed": True, "blocked": [], "clamped": plan["clamped"]},
        }
    base_preview_result = await _render_preview(
        config,
        source_raw,
        PP3Profile(),
        max_width=preview_width,
        label="predictive_base",
    )
    if not base_preview_result.get("success"):
        return {
            "error": "Failed to render base preview",
            "details": base_preview_result,
            "profile_path": str(profile_path),
            "parameters": parameters,
            "validation": {"allowed": True, "blocked": [], "clamped": plan["clamped"]},
        }

    before_after_name = f"predictive_compare_{source_raw.stem}_{int(time.time() * 1000)}.jpg"
    before_after_path = _build_before_after_preview(
        base_preview_path=base_preview_result.get("preview_path"),
        edited_preview_path=edited_preview_result.get("preview_path"),
        output_path=config.preview_dir / before_after_name,
    )

    return {
        "status": "verification_required",
        "decision": "verification_required",
        "decision_source": "auto_edit_predictive_prepare",
        "prepare_mode": "deterministic_routing_fallback",
        "raw_path": str(source_raw),
        "profile_path": str(profile_path),
        "base_preview_path": base_preview_result.get("preview_path"),
        "edited_preview_path": edited_preview_result.get("preview_path"),
        "preview_path": edited_preview_result.get("preview_path"),
        "before_after_path": before_after_path,
        "style": style,
        "intensity": intensity,
        "diagnosis": plan["diagnosis"],
        "parameters": parameters,
        "expected_effects": plan["expected_effect"],
        "planned_scores": plan["planned_scores"],
        "approved_curves_used": plan.get("approved_curves_used", []),
        "validation": {"allowed": True, "blocked": [], "clamped": plan["clamped"]},
        "blocked_controls_considered": plan["blocked_controls_considered"],
        "verification_packet": _verification_packet("primary subject"),
        "legacy_status": "legacy visual-move candidate generator is deprecated for autonomous default use",
    }


@mcp.tool()
async def auto_edit_predictive_prepare(
    ctx: Context,
    raw_path: str,
    style: str = "warm natural travel",
    intensity: str = "medium",
    user_brief: str | None = None,
    preview_width: int = 1024,
    diagnosis_override: dict[str, Any] | None = None,
    verification_feedback: dict[str, Any] | None = None,
) -> dict[str, Any] | ToolResult:
    """DO NOT USE FOR AUTONOMOUS EDITING. Deterministic fallback/debug prepare only.

    Final decision must happen in verify_predictive_edit. Use
    auto_edit_manifest_select_prepare + verify_predictive_edit instead.
    """
    if _has_explicit_verification_scores(verification_feedback):
        return {
            "error": "verification_feedback_not_allowed_in_prepare",
            "reason": "Use verify_predictive_edit for visual scoring and final decision.",
        }
    prepared = await _prepare_predictive_packet(
        ctx,
        raw_path=raw_path,
        style=style,
        intensity=intensity,
        user_brief=user_brief,
        preview_width=preview_width,
        diagnosis_override=diagnosis_override,
    )
    if prepared.get("status") != "verification_required":
        return prepared
    return await _tool_result_with_preview_images(
        prepared,
        max_width=preview_width,
        image_paths=[
            prepared.get("base_preview_path"),
            prepared.get("edited_preview_path"),
            prepared.get("before_after_path"),
        ],
    )


@mcp.tool()
async def get_compact_manifest_summary(ctx: Context) -> dict[str, Any]:
    """Return a compact agent-facing manifest summary for LLM control selection."""
    _ = get_config(ctx)
    return build_agent_manifest_summary()


@mcp.tool()
async def auto_edit_manifest_select_prepare(
    ctx: Context,
    raw_path: str,
    edit_plan: dict[str, Any],
    preview_width: int = 1024,
) -> dict[str, Any] | ToolResult:
    """Prepare a manifest-select edit from an LLM-supplied plan and return previews for verification."""
    prepared = await _prepare_manifest_select_packet(
        ctx,
        raw_path=raw_path,
        edit_plan=edit_plan,
        preview_width=preview_width,
    )
    if prepared.get("status") != "verification_required":
        return prepared
    return await _tool_result_with_preview_images(
        prepared,
        max_width=preview_width,
        image_paths=[
            prepared.get("base_preview_path"),
            prepared.get("edited_preview_path"),
            prepared.get("before_after_path"),
        ],
    )


@mcp.tool()
async def verify_predictive_edit(
    ctx: Context,
    raw_path: str,
    profile_path: str,
    base_preview_path: str,
    edited_preview_path: str,
    verification_observations: dict[str, Any],
    export: bool = False,
    before_after_path: str | None = None,
    preview_width: int = 1024,
) -> dict[str, Any] | ToolResult:
    """Verify a predictive edit from rendered previews and produce the final decision."""
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check
    try:
        source_raw = ensure_existing_file(raw_path)
    except FileNotFoundError as exc:
        return {"error": str(exc)}
    profile = Path(profile_path)
    if not profile.is_file():
        return {"error": f"Profile not found: {profile_path}"}
    if not Path(base_preview_path).is_file():
        return {"error": f"Base preview not found: {base_preview_path}"}
    if not Path(edited_preview_path).is_file():
        return {"error": f"Edited preview not found: {edited_preview_path}"}
    if not isinstance(verification_observations, dict):
        return {"error": "verification_observations_required"}

    missing_descriptions = _verify_required_descriptions(verification_observations)
    if missing_descriptions:
        return {"error": "verification_observations_required", "missing_fields": missing_descriptions}

    scores_raw = verification_observations.get("scores", {})
    if not isinstance(scores_raw, dict):
        scores_raw = {}
    normalized_input_scores = _normalize_verification_observed_scores(
        scores_raw,
        crop_dependency="secondary",
    )
    normalized_scores = _predictive_export_decision(True, normalized_input_scores)
    consistency = _consistency_checks(verification_observations, normalized_scores)
    decision = str(normalized_scores.get("decision", "proof_only"))

    resolved_before_after_path = before_after_path
    if not resolved_before_after_path:
        before_after_name = f"predictive_verify_{source_raw.stem}_{int(time.time() * 1000)}.jpg"
        resolved_before_after_path = _build_before_after_preview(
            base_preview_path=base_preview_path,
            edited_preview_path=edited_preview_path,
            output_path=config.preview_dir / before_after_name,
        )

    export_path: str | None = None
    if export and bool(normalized_scores.get("export_gate_passed")) and decision == "export":
        output_path = config.output_dir / f"{source_raw.stem}_predictive_verified.jpg"
        process_result = await run_rt_cli(
            rt_path=rt_check,
            input_path=source_raw,
            output_path=output_path,
            profiles=[profile],
            output_format="jpeg",
            jpeg_quality=config.default_jpeg_quality,
            bit_depth=16,
        )
        if process_result.get("success"):
            export_path = str(output_path)
        else:
            decision = "proof_only"

    output: dict[str, Any] = {
        "decision_source": "verify_predictive_edit",
        "raw_path": str(source_raw),
        "profile_path": str(profile),
        "base_preview_path": base_preview_path,
        "edited_preview_path": edited_preview_path,
        "before_after_path": resolved_before_after_path,
        "visual_verification_scores": normalized_scores,
        "verification_observations": verification_observations,
        "consistency_checks": consistency,
        "non_crop_edit_quality": normalized_scores.get("non_crop_edit_quality", "fail"),
        "decision": decision,
        "export_gate_passed": bool(normalized_scores.get("export_gate_passed")),
        "reason": str(
            normalized_scores.get(
                "non_crop_edit_quality_reason",
                "Verification scores did not support a stronger non-crop edit quality decision.",
            )
        ),
        "export_path": export_path,
    }
    if decision in {"proof_only", "failed_edit_quality", "crop_only_improvement"}:
        output["gate_message"] = _NON_OVERRIDEABLE_GATE_MESSAGE
        output["required_workflow"] = [
            "auto_edit_manifest_select_prepare",
            "verify_predictive_edit",
            "process_raw with verification_id",
        ]
    verification_marker = _write_verification_marker(
        config,
        raw_path=source_raw,
        profile_path=profile,
        decision=decision,
        export_gate_passed=bool(normalized_scores.get("export_gate_passed")),
        decision_source="verify_predictive_edit",
    )
    output["verification_id"] = verification_marker["verification_id"]
    output["verification_marker"] = verification_marker
    output["verified_export_allowed"] = verification_marker["verified_export_allowed"]
    return await _tool_result_with_preview_images(
        output,
        max_width=preview_width,
        image_paths=[base_preview_path, edited_preview_path, resolved_before_after_path],
    )


@mcp.tool()
async def auto_edit_predictive(
    ctx: Context,
    raw_path: str,
    style: str = "warm natural travel",
    intensity: str = "medium",
    user_brief: str | None = None,
    export: bool = False,
    preview_width: int = 1024,
    diagnosis_override: dict[str, Any] | None = None,
    verification_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """DO NOT USE FOR AUTONOMOUS EDITING. Backward-compatible fallback/debug wrapper.

    This wrapper intentionally cannot produce a final visual-verification
    decision. Use verify_predictive_edit for final scoring and export gating.
    """
    prepared = await _prepare_predictive_packet(
        ctx,
        raw_path=raw_path,
        style=style,
        intensity=intensity,
        user_brief=user_brief,
        preview_width=preview_width,
        diagnosis_override=diagnosis_override,
    )
    if isinstance(prepared, dict):
        prepared["deprecated"] = True
        prepared["fallback_only"] = True
        prepared["primary_prepare_tool"] = "auto_edit_manifest_select_prepare"
        prepared["deprecated_reason"] = (
            "auto_edit_predictive no longer accepts same-call verification/export decisions and remains only as the "
            "deterministic fallback/debug path. Call auto_edit_manifest_select_prepare, inspect previews, then call "
            "verify_predictive_edit."
        )
        if verification_feedback is not None:
            prepared["ignored_verification_feedback"] = True
        if export:
            prepared["export_blocked_until_verification"] = True
    return prepared


@mcp.tool()
async def critique_gate(
    ctx: Context,
    candidate_name: str,
    intended_style: str,
    preview_path: str | None = None,
    inferred_intent: dict[str, Any] | None = None,
    critique_standard: dict[str, Any] | str | None = None,
    editing_vision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a strict post-preview rubric contract for scoring and gating export.

    This tool does not score images itself. The LLM must inspect inline previews,
    fill the rubric honestly, and follow export/refine/reject rules.
    Params: preview_path, candidate_name, intended_style
    """
    checked_preview_path = preview_path
    warnings: list[str] = []
    if preview_path and not Path(preview_path).is_file():
        warnings.append(f"Preview path not found on disk: {preview_path}")
        checked_preview_path = preview_path

    result = build_critique_gate(
        checked_preview_path,
        candidate_name=candidate_name,
        intended_style=intended_style,
        inferred_intent=inferred_intent,
        critique_standard=critique_standard,
        editing_vision=editing_vision,
    )
    if warnings:
        result["warnings"] = warnings
    return result


@mcp.tool()
async def create_curation_plan(
    ctx: Context,
    directory: str,
    intent: str | None = None,
    recursive: bool = False,
    max_files: int | None = None,
) -> dict[str, Any]:
    """Create a selective curation workflow before editing a directory of RAW files.

    Does not edit files. Helps classify photos as reject/proof_only/edit_candidate/
    strong_keeper so weak images are not forced into final exports.
    Params: directory, intent, recursive, max_files
    """
    _ = get_config(ctx)
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return {"error": f"Directory not found: {directory}"}

    pattern = "**/*" if recursive else "*"
    discovered: list[str] = []
    for file_path in sorted(dir_path.glob(pattern)):
        if file_path.is_file() and file_path.suffix.lower() in RAW_EXTENSIONS:
            discovered.append(str(file_path))
            if max_files is not None and len(discovered) >= max_files:
                break

    plan = build_curation_plan(
        str(dir_path),
        intent=intent,
        recursive=recursive,
        max_files=max_files,
        discovered_files=discovered,
    )
    plan["sample_files"] = discovered[: min(10, len(discovered))]
    return plan


@mcp.tool()
async def read_exif(ctx: Context, file_path: str) -> dict[str, Any]:
    """Read EXIF metadata from a RAW image file.

    Returns camera settings (ISO, aperture, shutter speed, focal length, etc.)
    used when the photo was taken. Use this to make better decisions about
    processing parameters like noise reduction, lens correction, and white balance.
    Params: file_path
    """
    path = Path(file_path)

    if not path.is_file():
        return {"error": f"File not found: {file_path}"}

    exif = read_exif_data(path)
    result: dict[str, Any] = {**exif, "file_path": str(path)}
    result["recommendations"] = generate_recommendations(exif)
    return result


@mcp.tool()
async def generate_pp3_profile(
    ctx: Context,
    name: str,
    base_template: str | None = None,
    parameters: dict[str, Any] | None = None,
    device_preset: str | None = None,
    file_path: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Create a PP3 processing profile from parameters.

    Use this to generate a new processing profile for RAW development.
    Start with a base_template (e.g. "neutral", "warm_portrait") and
    override specific parameters, or build from scratch with parameters only.

    When device_preset is specified with file_path, the profile uses
    aspect-ratio-based cropping (correct behavior). Without file_path,
    it falls back to resize-only which may produce different results.
    Params: name, base_template, parameters, device_preset, file_path, description
    """
    config = get_config(ctx)
    templates_dir = _get_templates_dir()

    # Resolve device preset if specified
    preset_dict: dict[str, Any] | None = None
    if device_preset:
        preset_dict = get_preset(device_preset, config.custom_templates_dir)
        if preset_dict is None:
            return {"error": f"Device preset '{device_preset}' not found"}

    try:
        profile, output_path = _generate_profile(
            name=name,
            base_template=base_template,
            parameters=parameters,
            device_preset=preset_dict,
            templates_dir=templates_dir,
            custom_templates_dir=config.custom_templates_dir,
        )
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    # Override resize-only device preset with proper crop when source image is available
    if preset_dict and file_path:
        raw_path = Path(file_path)
        if raw_path.is_file():
            eff_w, eff_h = get_effective_dimensions(raw_path)
            if eff_w > 0 and eff_h > 0:
                apply_device_crop(profile, preset_dict, eff_w, eff_h)
                profile.save(output_path)

    summary = profile.to_dict()
    return {
        "profile_path": str(output_path),
        "name": name,
        "base_template": base_template,
        "device_preset": device_preset,
        "file_path": file_path,
        "description": description,
        "summary": summary,
    }


@mcp.tool()
async def process_raw(
    ctx: Context,
    file_path: str,
    profile_path: str,
    output_format: str = "jpeg",
    output_path: str | None = None,
    jpeg_quality: int | None = None,
    bit_depth: int = 16,
    include_preview: bool = True,
    preview_max_width: int = 600,
    verification_id: str | None = None,
    manual_override_unverified_export: bool = False,
) -> dict[str, Any] | ToolResult:
    """Process a RAW file with a PP3 processing profile.

    Use this to convert a RAW file to JPEG, TIFF, or PNG using a PP3 profile.
    The profile controls all processing parameters (exposure, white balance,
    sharpening, etc.). Autonomous/generated profiles must be verified first via
    auto_edit_manifest_select_prepare + verify_predictive_edit before export.
    Returns an inline thumbnail when include_preview is True.
    Params: file_path, profile_path, output_format, output_path, jpeg_quality, bit_depth,
    include_preview, preview_max_width, verification_id
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    raw_path = Path(file_path)
    pp3_path = Path(profile_path)

    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}
    if manual_override_unverified_export and not config.allow_manual_unverified_export:
        return {
            "error": "manual_override_not_available",
            "reason": "Manual unverified export is disabled for autonomous workflows.",
            "required_workflow": [
                "auto_edit_manifest_select_prepare",
                "verify_predictive_edit",
                "process_raw with verification_id",
            ],
            "gate_message": _NON_OVERRIDEABLE_GATE_MESSAGE,
        }

    if _profile_requires_verification(config, pp3_path):
        verified, marker, verification_error = _validate_export_verification(
            config,
            raw_path=raw_path,
            profile_path=pp3_path,
            verification_id=verification_id,
        )
        if not verified and not manual_override_unverified_export:
            return {
                "error": "verification_required_before_export",
                "reason": verification_error,
                "profile_path": str(pp3_path),
                "raw_path": str(raw_path),
                "verification_required_before_export": True,
                "recommended_prepare_tool": "auto_edit_manifest_select_prepare",
                "recommended_verify_tool": "verify_predictive_edit",
                "verification_marker": marker,
                "required_workflow": [
                    "auto_edit_manifest_select_prepare",
                    "verify_predictive_edit",
                    "process_raw with verification_id",
                ],
                "gate_message": _NON_OVERRIDEABLE_GATE_MESSAGE,
            }

    # Check for Crop+Resize conflict (RT 5.12 bug) — text-based to avoid
    # parser crash on Locallab profiles
    pp3_text = pp3_path.read_text(encoding="utf-8")
    crop_resize_warning = _check_crop_resize_conflict_text(pp3_text)

    # Determine output path
    quality = jpeg_quality if jpeg_quality is not None else config.default_jpeg_quality
    ext_map = {"jpeg": ".jpg", "tiff": ".tif", "png": ".png"}
    ext = ext_map.get(output_format.lower(), ".jpg")

    if output_path:
        out = Path(output_path)
    else:
        out = config.output_dir / f"{raw_path.stem}{ext}"

    # Ensure output directory exists
    out.parent.mkdir(parents=True, exist_ok=True)

    result = await run_rt_cli(
        rt_path=rt_check,
        input_path=raw_path,
        output_path=out,
        profiles=[pp3_path],
        output_format=output_format,
        jpeg_quality=quality,
        bit_depth=bit_depth,
    )

    if crop_resize_warning:
        result["warning"] = crop_resize_warning
    if manual_override_unverified_export and _profile_requires_verification(config, pp3_path):
        result["manual_override_unverified_export"] = True
        result["warning"] = (
            f"{result.get('warning', '')} Manual override bypassed verification gate for this export."
        ).strip()
    elif verification_id:
        result["verification_id"] = verification_id

    if include_preview:
        return await _maybe_attach_thumbnail(result, "output_path", preview_max_width)
    return result


@mcp.tool()
async def preview_raw(
    ctx: Context,
    file_path: str,
    profile_path: str | None = None,
    max_width: int | None = None,
    return_image: bool = True,
) -> dict[str, Any] | ToolResult:
    """Generate a small preview JPEG for visual analysis.

    Use this to create a quick preview of how a RAW file will look with
    specific processing settings. The preview is a small JPEG suitable for
    visual inspection of composition, exposure, and color. When return_image
    is True, the preview image is returned inline for the LLM to see.
    Params: file_path, profile_path, max_width, return_image
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}

    width = max_width if max_width is not None else config.preview_max_width

    # When a profile path is given, pass the Path directly to avoid parsing
    # (prevents crash on Locallab profiles).  Without a path, use empty profile.
    profile: PP3Profile | Path
    if profile_path:
        pp3_path = Path(profile_path)
        if not pp3_path.is_file():
            return {"error": f"Profile not found: {profile_path}"}
        profile = pp3_path
    else:
        profile = PP3Profile()

    result = await _render_preview(config, raw_path, profile, max_width=width)

    if result.get("success") and return_image:
        preview_path = result.get("preview_path", "")
        try:
            img_content = await _preview_to_image_content(preview_path, width)
            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(result, indent=2)),
                    img_content,
                ],
                structured_content=result,
            )
        except Exception:  # noqa: BLE001
            logger.debug("Image return failed for %s", preview_path, exc_info=True)

    return result


# ---------------------------------------------------------------------------
# Phase 2 Tools — Templates & Presets
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_templates(ctx: Context) -> dict[str, Any]:
    """List all available PP3 processing templates (built-in and custom).

    Use this to discover which templates are available for apply_template
    or as a base_template for generate_pp3_profile.
    Returns: dict with built_in and custom template lists.
    """
    config = get_config(ctx)
    templates_dir = _get_templates_dir()

    built_in: list[dict[str, str]] = []
    for pp3_file in sorted(templates_dir.glob("*.pp3")):
        built_in.append({"name": pp3_file.stem, "source": "built_in", "path": str(pp3_file)})

    custom: list[dict[str, str]] = []
    for pp3_file in sorted(config.custom_templates_dir.glob("*.pp3")):
        custom.append({"name": pp3_file.stem, "source": "custom", "path": str(pp3_file)})

    return {"built_in": built_in, "custom": custom, "total": len(built_in) + len(custom)}


@mcp.tool()
async def apply_template(
    ctx: Context,
    file_path: str,
    template_name: str,
    output_format: str = "jpeg",
    output_dir: str | None = None,
    device_preset: str | None = None,
    include_preview: bool = True,
    preview_max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Apply a built-in or custom PP3 template to a RAW file and process it.

    Use this for quick processing with a predefined style. Optionally apply
    a device preset for crop/resize on top of the template. Returns an inline
    thumbnail when include_preview is True.
    Params: file_path, template_name, output_format, output_dir, device_preset,
    include_preview, preview_max_width
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}

    templates_dir = _get_templates_dir()

    # Load template
    template_path = config.custom_templates_dir / f"{template_name}.pp3"
    if not template_path.is_file():
        template_path = templates_dir / f"{template_name}.pp3"
    if not template_path.is_file():
        return {"error": f"Template '{template_name}' not found"}

    # Build a SINGLE combined PP3 (RT 5.12 can crash merging multiple PP3s)
    combined = PP3Profile()
    combined.load(template_path)

    combined_path: Path | None = None
    eff_w, eff_h = 0, 0
    if device_preset:
        preset_dict = get_preset(device_preset, config.custom_templates_dir)
        if preset_dict is None:
            return {"error": f"Device preset '{device_preset}' not found"}

        # Read source image dimensions for correct crop calculation
        eff_w, eff_h = get_effective_dimensions(raw_path)

        if eff_w > 0 and eff_h > 0:
            # Calculate correct aspect-ratio crop using source dimensions
            apply_device_crop(combined, preset_dict, eff_w, eff_h)
        else:
            # Fallback: resize only (no crop possible without dimensions)
            from rawtherapee_mcp.pp3_generator import apply_device_preset

            apply_device_preset(combined, preset_dict)
            logger.warning(
                "Could not read source dimensions for %s (got %dx%d), using resize-only",
                raw_path.name,
                eff_w,
                eff_h,
            )

    # Save combined PP3 to a temp file
    timestamp = int(time.time() * 1000)
    combined_path = config.preview_dir / f"_combined_{template_name}_{timestamp}.pp3"
    combined.save(combined_path)

    # Determine output path
    out_dir = Path(output_dir) if output_dir else config.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ext_map = {"jpeg": ".jpg", "tiff": ".tif", "png": ".png"}
    ext = ext_map.get(output_format.lower(), ".jpg")
    output_path = out_dir / f"{raw_path.stem}_{template_name}{ext}"

    result = await run_rt_cli(
        rt_path=rt_check,
        input_path=raw_path,
        output_path=output_path,
        profiles=[combined_path],
        output_format=output_format,
        jpeg_quality=config.default_jpeg_quality,
    )

    # Add diagnostic info for device preset results
    if device_preset:
        result["effective_dimensions"] = [eff_w, eff_h]
        result["device_crop_applied"] = eff_w > 0 and eff_h > 0
        if not result.get("success"):
            result["combined_pp3_content"] = combined.dumps()

    # Clean up temporary combined PP3
    if combined_path:
        try:
            combined_path.unlink(missing_ok=True)
        except OSError:
            pass

    if include_preview:
        return await _maybe_attach_thumbnail(result, "output_path", preview_max_width)
    return result


@mcp.tool()
async def list_device_presets(ctx: Context) -> dict[str, Any]:
    """List all device/format crop and resize presets.

    Use this to discover available presets for mobile wallpapers, desktop
    wallpapers, and photo aspect ratios. Presets can be applied when
    generating profiles or processing images.
    Returns: dict with presets grouped by category (mobile, desktop, photo_formats, custom).
    """
    config = get_config(ctx)
    presets = get_all_presets(config.custom_templates_dir)
    return {"presets": presets}


@mcp.tool()
async def adjust_profile(
    ctx: Context,
    profile_path: str,
    adjustments: dict[str, Any],
    save_as: str | None = None,
) -> dict[str, Any]:
    """DO NOT USE FOR AUTONOMOUS EDITING. DO NOT USE FOR FINAL EXPORT.

    Modify specific parameters in an existing PP3 profile.

    Use this to tweak individual settings without recreating the entire profile.
    Only the specified parameters are changed; all other settings are preserved.
    Manual/debug tool only for autonomous workflows. Do not use this as the
    final autonomous edit path without verify_predictive_edit.

    Accepts both friendly parameter names (e.g. {"crop": {"width": 3108}}) and
    raw PP3 section/key pairs (e.g. {"Crop": {"W": "3108", "H": "6732"}}).
    Unrecognized group names are treated as raw PP3 section names.
    Params: profile_path, adjustments, save_as
    """
    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    profile = PP3Profile()
    profile.load(pp3_path)

    apply_parameters(profile, adjustments, raw_fallback=True)

    if save_as:
        output_path = pp3_path.parent / save_as
        if not output_path.suffix:
            output_path = output_path.with_suffix(".pp3")
    else:
        output_path = pp3_path

    profile.save(output_path)

    return {
        "profile_path": str(output_path),
        "adjustments_applied": adjustments,
        "summary": profile.to_dict(),
        "legacy_status": "manual_debug_only",
        "verification_required_before_export": True,
        "recommended_next_tool": "verify_predictive_edit",
        "recommended_prepare_tool": "auto_edit_manifest_select_prepare",
    }


@mcp.tool()
async def read_profile(ctx: Context, profile_path: str) -> dict[str, Any]:
    """Display contents of a PP3 profile in human-readable format.

    Use this to inspect what settings a profile contains before applying it.
    Returns all active sections and their key-value pairs.
    Params: profile_path
    """
    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    profile = PP3Profile()
    profile.load(pp3_path)

    return {
        "profile_path": str(pp3_path),
        "sections": profile.to_dict(),
        "section_count": len(profile.sections()),
    }


@mcp.tool()
async def compare_profiles(
    ctx: Context,
    profile_a: str,
    profile_b: str,
    file_path: str | None = None,
    include_preview: bool = False,
    preview_max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Compare two PP3 profiles and show the differences.

    Use this to understand how two profiles differ before choosing between them,
    or to see what changed after adjustments. When file_path and include_preview
    are provided, renders both profiles as inline images for visual comparison.
    Params: profile_a, profile_b, file_path, include_preview, preview_max_width
    """
    path_a = Path(profile_a)
    path_b = Path(profile_b)

    if not path_a.is_file():
        return {"error": f"Profile A not found: {profile_a}"}
    if not path_b.is_file():
        return {"error": f"Profile B not found: {profile_b}"}

    prof_a = PP3Profile()
    prof_a.load(path_a)

    prof_b = PP3Profile()
    prof_b.load(path_b)

    diff = prof_a.diff(prof_b)

    result: dict[str, Any] = {
        "profile_a": str(path_a),
        "profile_b": str(path_b),
        **diff,
    }

    if file_path and include_preview:
        config = get_config(ctx)
        rt_check = _require_rt(config)
        raw_path = Path(file_path)

        if not isinstance(rt_check, dict) and raw_path.is_file():
            # Pass Paths to avoid parser crash on Locallab profiles
            preview_a = await _render_preview(config, raw_path, path_a, max_width=preview_max_width, label="cmp_a")
            preview_b = await _render_preview(config, raw_path, path_b, max_width=preview_max_width, label="cmp_b")
            result["preview_a"] = preview_a
            result["preview_b"] = preview_b

            if preview_a.get("success") and preview_b.get("success"):
                try:
                    img_a = await _preview_to_image_content(preview_a["preview_path"], preview_max_width)
                    img_b = await _preview_to_image_content(preview_b["preview_path"], preview_max_width)
                    return ToolResult(
                        content=[
                            TextContent(type="text", text=json.dumps(result, indent=2)),
                            img_a,
                            img_b,
                        ],
                        structured_content=result,
                    )
                except Exception:  # noqa: BLE001
                    logger.debug("Image return failed for compare preview", exc_info=True)

    return result


# ---------------------------------------------------------------------------
# Phase 3 Tools — CRUD & Batch
# ---------------------------------------------------------------------------


@mcp.tool()
async def save_template(
    ctx: Context,
    profile_path: str,
    name: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Save an existing PP3 profile as a reusable custom template.

    Use this to save a tuned profile so it can be reused later with
    apply_template or as a base_template for generate_pp3_profile.
    Params: profile_path, name, description
    """
    config = get_config(ctx)
    pp3_path = Path(profile_path)

    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    import shutil

    dest = config.custom_templates_dir / f"{name}.pp3"
    shutil.copy2(str(pp3_path), str(dest))

    return {
        "template_name": name,
        "template_path": str(dest),
        "description": description,
        "source_path": str(pp3_path),
    }


@mcp.tool()
async def create_template_from_description(
    ctx: Context,
    name: str,
    description: str,
    reference_image_path: str | None = None,
) -> dict[str, Any]:
    """Create a new PP3 template from a natural language style description.

    Use this to create a template when the user describes a look in words
    (e.g. "warm golden hour tones, film-like grain"). You (Claude) interpret
    the description and call generate_pp3_profile with appropriate parameters.
    This tool creates a neutral base template with the given name and description.
    Params: name, description, reference_image_path
    """
    config = get_config(ctx)
    templates_dir = _get_templates_dir()

    profile, output_path = _generate_profile(
        name=name,
        base_template=None,
        parameters=None,
        device_preset=None,
        templates_dir=templates_dir,
        custom_templates_dir=config.custom_templates_dir,
    )

    result: dict[str, Any] = {
        "template_name": name,
        "template_path": str(output_path),
        "description": description,
        "reference_image_path": reference_image_path,
        "note": "Template created with neutral settings. Use adjust_profile to refine parameters.",
        "recommended_workflow": [
            "1. Use adjust_profile() to set processing parameters based on the description",
            "2. Use preview_raw() to verify the result visually",
            "3. Use save_template() to save the finalized profile",
        ],
        "summary": profile.to_dict(),
    }

    # If a reference image is provided, include EXIF-based recommendations
    if reference_image_path:
        ref_path = Path(reference_image_path)
        if ref_path.is_file():
            exif = read_exif_data(ref_path)
            if "error" not in exif:
                recs = generate_recommendations(exif)
                result["exif_recommendations"] = recs

    return result


@mcp.tool()
async def delete_template(ctx: Context, template_name: str) -> dict[str, Any]:
    """Delete a custom PP3 template.

    Use this to remove a custom template that is no longer needed.
    Built-in templates cannot be deleted.
    Params: template_name
    """
    config = get_config(ctx)
    templates_dir = _get_templates_dir()

    # Check if it's a built-in template
    builtin_path = templates_dir / f"{template_name}.pp3"
    if builtin_path.is_file():
        return {"error": f"Cannot delete built-in template '{template_name}'"}

    custom_path = config.custom_templates_dir / f"{template_name}.pp3"
    if not custom_path.is_file():
        return {"error": f"Custom template '{template_name}' not found"}

    custom_path.unlink()
    return {"deleted": template_name, "path": str(custom_path)}


@mcp.tool()
async def add_device_preset_tool(
    ctx: Context,
    preset_id: str,
    name: str,
    width: int,
    height: int,
    category: str = "custom",
) -> dict[str, Any]:
    """Create and persist a custom device/format preset for cropping and resizing.

    Use this to add a preset for a device or format not in the built-in list.
    Custom presets are saved to disk and available in future sessions.
    Params: preset_id, name, width, height, category
    """
    config = get_config(ctx)
    add_custom_preset(preset_id, name, width, height, category, config.custom_templates_dir)
    return {
        "preset_id": preset_id,
        "name": name,
        "width": width,
        "height": height,
        "category": category,
    }


@mcp.tool()
async def delete_device_preset(ctx: Context, preset_id: str) -> dict[str, Any]:
    """Delete a custom device preset.

    Use this to remove a custom device preset. Built-in presets cannot be deleted.
    Params: preset_id
    """
    if is_builtin_preset(preset_id):
        return {"error": f"Cannot delete built-in preset '{preset_id}'"}

    config = get_config(ctx)
    deleted = delete_custom_preset(preset_id, config.custom_templates_dir)
    if not deleted:
        return {"error": f"Custom preset '{preset_id}' not found"}

    return {"deleted": preset_id}


@mcp.tool()
async def batch_process(
    ctx: Context,
    file_paths: list[str],
    profile_path: str,
    output_format: str = "jpeg",
    output_dir: str | None = None,
    device_preset: str | None = None,
) -> dict[str, Any]:
    """Process multiple RAW files with the same PP3 profile.

    Use this for bulk processing of a set of RAW files with identical settings.
    Params: file_paths, profile_path, output_format, output_dir, device_preset
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    # Check for Crop+Resize conflict (RT 5.12 bug)
    base_check = PP3Profile()
    base_check.load(pp3_path)
    crop_resize_warning = _check_crop_resize_conflict(base_check)

    out_dir = Path(output_dir) if output_dir else config.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve device preset if specified
    preset_dict: dict[str, Any] | None = None
    if device_preset:
        preset_dict = get_preset(device_preset, config.custom_templates_dir)
        if preset_dict is None:
            return {"error": f"Device preset '{device_preset}' not found"}

    ext_map = {"jpeg": ".jpg", "tiff": ".tif", "png": ".png"}
    ext = ext_map.get(output_format.lower(), ".jpg")

    # Load the base profile once
    base_profile = PP3Profile()
    base_profile.load(pp3_path)

    results: list[dict[str, Any]] = []
    temp_paths: list[Path] = []

    for fp in file_paths:
        raw_path = Path(fp)
        if not raw_path.is_file():
            results.append({"file": fp, "error": f"File not found: {fp}"})
            continue

        # Build a SINGLE combined PP3 per file (RT 5.12 can't merge multiple PP3s)
        combined = PP3Profile()
        combined.load(pp3_path)

        if preset_dict:
            # Calculate per-file crop from source dimensions
            eff_w, eff_h = get_effective_dimensions(raw_path)

            if eff_w > 0 and eff_h > 0:
                apply_device_crop(combined, preset_dict, eff_w, eff_h)
            else:
                from rawtherapee_mcp.pp3_generator import apply_device_preset as _apply_preset

                _apply_preset(combined, preset_dict)

        ts = int(time.time() * 1000)
        combined_path = config.preview_dir / f"_batch_{raw_path.stem}_{ts}.pp3"
        combined.save(combined_path)
        temp_paths.append(combined_path)

        output_path = out_dir / f"{raw_path.stem}{ext}"
        result = await run_rt_cli(
            rt_path=rt_check,
            input_path=raw_path,
            output_path=output_path,
            profiles=[combined_path],
            output_format=output_format,
            jpeg_quality=config.default_jpeg_quality,
        )
        result["file"] = fp
        results.append(result)

    # Clean up per-file temp PP3s
    for tp in temp_paths:
        try:
            tp.unlink(missing_ok=True)
        except OSError:
            pass

    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded

    batch_result: dict[str, Any] = {
        "results": results,
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
    }
    if crop_resize_warning:
        batch_result["warning"] = crop_resize_warning
    return batch_result


@mcp.tool()
async def list_output_files(
    ctx: Context,
    directory: str | None = None,
    format_filter: str | None = None,
) -> dict[str, Any]:
    """List processed output files in the output directory.

    Use this to see what images have been processed and are available.
    Params: directory, format_filter (jpeg, tiff, png)
    """
    config = get_config(ctx)
    dir_path = Path(directory) if directory else config.output_dir

    if not dir_path.is_dir():
        return {"error": f"Directory not found: {dir_path}"}

    ext_filter: set[str] | None = None
    if format_filter:
        filter_map: dict[str, set[str]] = {
            "jpeg": {".jpg", ".jpeg"},
            "tiff": {".tif", ".tiff"},
            "png": {".png"},
        }
        ext_filter = filter_map.get(format_filter.lower())
        if ext_filter is None:
            return {"error": f"Unknown format filter: {format_filter}. Use 'jpeg', 'tiff', or 'png'."}

    files: list[dict[str, Any]] = []
    image_exts = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}

    for file_path in sorted(dir_path.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in image_exts:
            continue
        if ext_filter and file_path.suffix.lower() not in ext_filter:
            continue

        stat = file_path.stat()
        files.append(
            {
                "path": str(file_path),
                "filename": file_path.name,
                "size": stat.st_size,
                "format": file_path.suffix.lower().lstrip("."),
                "modified": stat.st_mtime,
            }
        )

    return {"files": files, "count": len(files), "directory": str(dir_path)}


@mcp.tool()
async def get_image_info(
    ctx: Context,
    file_path: str,
    include_thumbnail: bool = True,
    thumbnail_max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Get technical information about a processed image file.

    Use this to check dimensions, format, file size, and bit depth of
    JPEG, TIFF, or PNG output files. When include_thumbnail is True,
    returns an inline thumbnail for visual verification.
    Params: file_path, include_thumbnail, thumbnail_max_width
    """
    path = Path(file_path)
    # Brief delay to allow file handle release after recent processing
    await asyncio.sleep(0.5)
    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(_get_image_info, path),
            timeout=10.0,
        )
    except TimeoutError:
        return {"error": f"Timeout reading {file_path} — file may be locked by another process"}

    if include_thumbnail and "error" not in info:
        try:
            thumb_bytes = await asyncio.to_thread(generate_thumbnail, path, thumbnail_max_width)
            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(info, indent=2)),
                    MCPImage(data=thumb_bytes, format="jpeg").to_image_content(),
                ],
                structured_content=info,
            )
        except Exception:  # noqa: BLE001
            logger.debug("Thumbnail generation failed for %s", file_path, exc_info=True)

    return info


# ---------------------------------------------------------------------------
# Phase 5 Tools — Visual Analysis & Advanced Processing
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_histogram(
    ctx: Context,
    file_path: str,
    include_svg: bool = True,
) -> dict[str, Any]:
    """Compute RGB histogram and image statistics for a processed image.

    Analyzes the tonal distribution of a JPEG, TIFF, or PNG image. Returns
    per-channel histograms (256 bins), statistics (mean, median, std_dev,
    min, max), and clipping percentages. Optionally includes an SVG
    visualization.
    Params: file_path, include_svg
    """
    path = Path(file_path)
    if not path.is_file():
        return {"error": f"Image not found: {file_path}"}

    try:
        data = await asyncio.to_thread(compute_histogram, path)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Histogram computation failed: {exc}"}

    result: dict[str, Any] = {
        "file_path": str(path),
        "statistics": data["statistics"],
        "clipping": data["clipping"],
        "total_pixels": data["total_pixels"],
    }

    if include_svg:
        result["svg"] = render_histogram_svg(data)

    return result


@mcp.tool()
async def preview_before_after(
    ctx: Context,
    file_path: str,
    profile_path: str,
    max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Generate before/after preview images to compare processing effects.

    Renders a RAW file twice: once with default (neutral) settings and once
    with the specified profile. Returns both images inline for the LLM to
    visually compare the difference.
    Params: file_path, profile_path, max_width
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}

    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    # Render "before" (neutral profile — no Locallab, safe to use PP3Profile)
    before_profile = PP3Profile()
    before_result = await _render_preview(config, raw_path, before_profile, max_width=max_width, label="before")

    # Render "after" — pass Path to avoid parser crash on Locallab profiles
    after_result = await _render_preview(config, raw_path, pp3_path, max_width=max_width, label="after")

    metadata: dict[str, Any] = {
        "file_path": str(raw_path),
        "profile_path": str(pp3_path),
        "before": before_result,
        "after": after_result,
    }

    # Return with inline images if both succeeded
    if before_result.get("success") and after_result.get("success"):
        try:
            img_before = await _preview_to_image_content(before_result["preview_path"], max_width)
            img_after = await _preview_to_image_content(after_result["preview_path"], max_width)
            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(metadata, indent=2)),
                    img_before,
                    img_after,
                ],
                structured_content=metadata,
            )
        except Exception:  # noqa: BLE001
            logger.debug("Image return failed for before/after preview", exc_info=True)

    return metadata


@mcp.tool()
async def adjust_crop_position(
    ctx: Context,
    profile_path: str,
    file_path: str,
    horizontal: str = "center",
    vertical: str = "center",
    include_preview: bool = True,
    preview_max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Reposition an existing crop within the source image bounds.

    Moves the crop area defined in a PP3 profile to a new position. Accepts
    named positions ('left', 'center', 'right' for horizontal; 'top',
    'center', 'bottom' for vertical) or pixel offsets as strings.
    The profile is updated in-place.
    Params: profile_path, file_path, horizontal, vertical, include_preview,
    preview_max_width
    """
    config = get_config(ctx)

    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}

    profile = PP3Profile()
    profile.load(pp3_path)

    if profile.get("Crop", "Enabled") != "true":
        return {"error": "No crop is enabled in this profile"}

    try:
        crop_w = int(profile.get("Crop", "W"))
        crop_h = int(profile.get("Crop", "H"))
    except (ValueError, KeyError):
        return {"error": "Could not read crop dimensions from profile"}

    if crop_w <= 0 or crop_h <= 0:
        return {"error": f"Invalid crop dimensions: {crop_w}x{crop_h}"}

    # Get source image dimensions
    src_w, src_h = get_effective_dimensions(raw_path)
    if src_w == 0 or src_h == 0:
        return {"error": f"Could not determine source image dimensions for {file_path}"}

    # Calculate new X position
    max_x = max(0, src_w - crop_w)
    if horizontal == "left":
        new_x = 0
    elif horizontal == "center":
        new_x = max_x // 2
    elif horizontal == "right":
        new_x = max_x
    else:
        try:
            new_x = max(0, min(int(horizontal), max_x))
        except ValueError:
            return {"error": f"Invalid horizontal position: {horizontal}"}

    # Calculate new Y position
    max_y = max(0, src_h - crop_h)
    if vertical == "top":
        new_y = 0
    elif vertical == "center":
        new_y = max_y // 2
    elif vertical == "bottom":
        new_y = max_y
    else:
        try:
            new_y = max(0, min(int(vertical), max_y))
        except ValueError:
            return {"error": f"Invalid vertical position: {vertical}"}

    # Update profile in-place
    profile.set("Crop", "X", str(new_x))
    profile.set("Crop", "Y", str(new_y))
    profile.save(pp3_path)

    result: dict[str, Any] = {
        "profile_path": str(pp3_path),
        "crop_x": new_x,
        "crop_y": new_y,
        "crop_w": crop_w,
        "crop_h": crop_h,
        "source_width": src_w,
        "source_height": src_h,
    }

    if include_preview:
        rt_check = _require_rt(config)
        if isinstance(rt_check, dict):
            return result

        # Profile was just saved to pp3_path — pass Path to avoid parser
        # issues on re-load (e.g. Locallab sections)
        preview_result = await _render_preview(config, raw_path, pp3_path, max_width=preview_max_width, label="crop")
        result["preview"] = preview_result

        if preview_result.get("success"):
            try:
                img = await _preview_to_image_content(preview_result["preview_path"], preview_max_width)
                return ToolResult(
                    content=[
                        TextContent(type="text", text=json.dumps(result, indent=2)),
                        img,
                    ],
                    structured_content=result,
                )
            except Exception:  # noqa: BLE001
                logger.debug("Image return failed for crop preview", exc_info=True)

    return result


@mcp.tool()
async def preview_exposure_bracket(
    ctx: Context,
    file_path: str,
    profile_path: str | None = None,
    stops: list[float] | None = None,
    max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Simulate exposure bracketing by rendering multiple EV previews.

    Generates preview images at different exposure compensation values.
    Useful for determining the optimal exposure before committing to a
    full-resolution render.
    Params: file_path, profile_path, stops, max_width
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}

    if stops is None:
        stops = [-1.0, 0.0, 1.0]

    # Load base profile
    base_profile = PP3Profile()
    if profile_path:
        pp3_path = Path(profile_path)
        if not pp3_path.is_file():
            return {"error": f"Profile not found: {profile_path}"}
        base_profile.load(pp3_path)

    # Get current exposure compensation
    base_comp_str = base_profile.get("Exposure", "Compensation")
    try:
        base_comp = float(base_comp_str) if base_comp_str else 0.0
    except ValueError:
        base_comp = 0.0

    previews: list[dict[str, Any]] = []
    image_contents: list[Any] = []

    for stop in stops:
        variant = base_profile.copy()
        variant.set("Exposure", "Compensation", str(base_comp + stop))

        label = f"ev{stop:+.1f}".replace(".", "_").replace("+", "p").replace("-", "m")
        result = await _render_preview(config, raw_path, variant, max_width=max_width, label=label)
        result["ev_offset"] = stop
        result["total_compensation"] = base_comp + stop
        previews.append(result)

        if result.get("success"):
            try:
                image_contents.append(await _preview_to_image_content(result["preview_path"], max_width))
            except Exception:  # noqa: BLE001
                logger.debug("Image return failed for EV %+.1f", stop, exc_info=True)

    metadata: dict[str, Any] = {
        "file_path": str(raw_path),
        "base_compensation": base_comp,
        "stops": stops,
        "previews": previews,
    }

    if image_contents:
        try:
            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(metadata, indent=2)),
                    *image_contents,
                ],
                structured_content=metadata,
            )
        except Exception:  # noqa: BLE001
            logger.debug("ToolResult creation failed for exposure bracket", exc_info=True)

    return metadata


_WB_TEMPERATURES: dict[str, int] = {
    "Daylight": 5500,
    "Cloudy": 6500,
    "Shade": 7500,
    "Tungsten": 3200,
    "Fluorescent": 4000,
    "Flash": 5500,
    "Camera": 0,
    "Auto": 0,
    "Custom": 0,
}


@mcp.tool()
async def preview_white_balance(
    ctx: Context,
    file_path: str,
    profile_path: str | None = None,
    presets: list[str] | None = None,
    max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Preview different white balance presets on a RAW file.

    Renders the same image with multiple white balance settings so the LLM
    can compare and recommend the best one. Each preview includes an
    approximate Kelvin temperature for reference.
    Params: file_path, profile_path, presets, max_width
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}

    if presets is None:
        presets = ["Daylight", "Cloudy", "Shade", "Tungsten", "Fluorescent"]

    base_profile = PP3Profile()
    if profile_path:
        pp3_path = Path(profile_path)
        if not pp3_path.is_file():
            return {"error": f"Profile not found: {profile_path}"}
        base_profile.load(pp3_path)

    previews: list[dict[str, Any]] = []
    image_contents: list[Any] = []

    for preset_name in presets:
        variant = base_profile.copy()
        variant.set("White Balance", "Setting", preset_name)

        label = f"wb_{preset_name.lower()}"
        result = await _render_preview(config, raw_path, variant, max_width=max_width, label=label)
        result["wb_preset"] = preset_name
        result["temperature_k"] = _WB_TEMPERATURES.get(preset_name, 0)
        previews.append(result)

        if result.get("success"):
            try:
                image_contents.append(await _preview_to_image_content(result["preview_path"], max_width))
            except Exception:  # noqa: BLE001
                logger.debug("Image return failed for WB %s", preset_name, exc_info=True)

    metadata: dict[str, Any] = {
        "file_path": str(raw_path),
        "presets": presets,
        "previews": previews,
    }

    if image_contents:
        try:
            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(metadata, indent=2)),
                    *image_contents,
                ],
                structured_content=metadata,
            )
        except Exception:  # noqa: BLE001
            logger.debug("ToolResult creation failed for WB preview", exc_info=True)

    return metadata


@mcp.tool()
async def export_multi_device(
    ctx: Context,
    file_path: str,
    profile_path: str,
    device_presets: list[str],
    output_format: str = "jpeg",
    output_dir: str | None = None,
    include_previews: bool = False,
    preview_max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Export a RAW file optimized for multiple devices in one call.

    Processes the same RAW file with device-specific crop/resize for each
    target device. Output filenames include the device name. Set
    include_previews=True to return inline thumbnails per export.
    Params: file_path, profile_path, device_presets, output_format, output_dir,
    include_previews, preview_max_width
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}

    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    out_dir = Path(output_dir) if output_dir else config.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ext_map = {"jpeg": ".jpg", "tiff": ".tif", "png": ".png"}
    ext = ext_map.get(output_format.lower(), ".jpg")

    base_profile = PP3Profile()
    base_profile.load(pp3_path)

    # Get source dimensions once
    src_w, src_h = get_effective_dimensions(raw_path)

    results: list[dict[str, Any]] = []
    temp_paths: list[Path] = []
    image_contents: list[Any] = []

    for preset_name in device_presets:
        preset_dict = get_preset(preset_name, config.custom_templates_dir)
        if preset_dict is None:
            results.append({"device": preset_name, "error": f"Device preset '{preset_name}' not found"})
            continue

        combined = base_profile.copy()

        if src_w > 0 and src_h > 0:
            apply_device_crop(combined, preset_dict, src_w, src_h)
        else:
            from rawtherapee_mcp.pp3_generator import apply_device_preset as _apply_preset

            _apply_preset(combined, preset_dict)

        ts = int(time.time() * 1000)
        combined_path = config.preview_dir / f"_multi_{preset_name}_{ts}.pp3"
        combined.save(combined_path)
        temp_paths.append(combined_path)

        safe_name = preset_name.replace(" ", "_").lower()
        output_path = out_dir / f"{raw_path.stem}_{safe_name}{ext}"

        result = await run_rt_cli(
            rt_path=rt_check,
            input_path=raw_path,
            output_path=output_path,
            profiles=[combined_path],
            output_format=output_format,
            jpeg_quality=config.default_jpeg_quality,
        )
        result["device"] = preset_name
        results.append(result)

        if include_previews and result.get("success") and result.get("output_path"):
            try:
                image_contents.append(await _preview_to_image_content(result["output_path"], preview_max_width))
            except Exception:  # noqa: BLE001
                logger.debug("Thumbnail failed for %s export", preset_name, exc_info=True)

    # Clean up temp PP3s
    for tp in temp_paths:
        try:
            tp.unlink(missing_ok=True)
        except OSError:
            pass

    succeeded = sum(1 for r in results if r.get("success"))
    metadata: dict[str, Any] = {
        "file_path": str(raw_path),
        "results": results,
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
    }

    if image_contents:
        try:
            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(metadata, indent=2)),
                    *image_contents,
                ],
                structured_content=metadata,
            )
        except Exception:  # noqa: BLE001
            logger.debug("ToolResult creation failed for export_multi_device", exc_info=True)

    return metadata


@mcp.tool()
async def batch_preview(
    ctx: Context,
    file_paths: list[str],
    profile_path: str | None = None,
    max_width: int = 300,
    max_images: int = 12,
    include_exif: bool = False,
) -> dict[str, Any] | ToolResult:
    """Generate small preview thumbnails for multiple RAW files.

    Creates a batch of preview images for quick visual scanning. Useful for
    selecting images from a series or verifying batch settings before
    full-resolution processing. Set include_exif=True to attach a short EXIF
    summary (ISO, aperture, shutter speed, focal length) per image.
    Params: file_paths, profile_path, max_width, max_images, include_exif
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    # When a profile path is given, pass Path to avoid parser crash on
    # Locallab profiles.  Without a path, use empty PP3Profile.
    base_profile: PP3Profile | Path
    if profile_path:
        pp3_path = Path(profile_path)
        if not pp3_path.is_file():
            return {"error": f"Profile not found: {profile_path}"}
        base_profile = pp3_path
    else:
        base_profile = PP3Profile()

    capped = file_paths[:max_images]
    previews: list[dict[str, Any]] = []
    image_contents: list[Any] = []

    for fp in capped:
        raw_path = Path(fp)
        if not raw_path.is_file():
            previews.append({"file": fp, "error": f"File not found: {fp}"})
            continue

        result = await _render_preview(config, raw_path, base_profile, max_width=max_width, label="batch")
        result["file"] = fp

        if include_exif:
            exif = read_exif_data(raw_path)
            if "error" not in exif:
                result["exif_summary"] = {
                    "iso": exif.get("iso", ""),
                    "aperture": exif.get("aperture", ""),
                    "shutter_speed": exif.get("shutter_speed", ""),
                    "focal_length": exif.get("focal_length", ""),
                }

        previews.append(result)

        if result.get("success"):
            try:
                image_contents.append(await _preview_to_image_content(result["preview_path"], max_width))
            except Exception:  # noqa: BLE001
                logger.debug("Image return failed for batch preview %s", fp, exc_info=True)

    metadata: dict[str, Any] = {
        "previews": previews,
        "total": len(capped),
        "succeeded": sum(1 for p in previews if p.get("success")),
        "capped": len(file_paths) > max_images,
    }

    if image_contents:
        try:
            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(metadata, indent=2)),
                    *image_contents,
                ],
                structured_content=metadata,
            )
        except Exception:  # noqa: BLE001
            logger.debug("ToolResult creation failed for batch preview", exc_info=True)

    return metadata


@mcp.tool()
async def analyze_image(
    ctx: Context,
    file_path: str,
    include_histogram: bool = True,
    include_thumbnail: bool = True,
    thumbnail_max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Comprehensive single-call analysis of a RAW or processed image.

    Combines EXIF metadata, structured processing recommendations, histogram
    statistics, and an inline thumbnail into one response. Use this for the
    initial assessment of an image before deciding on processing settings.
    Params: file_path, include_histogram, include_thumbnail, thumbnail_max_width
    """
    path = Path(file_path)
    if not path.is_file():
        return {"error": f"Image not found: {file_path}"}

    result: dict[str, Any] = {"file_path": str(path)}

    # EXIF data + recommendations
    exif = read_exif_data(path)
    result["exif"] = exif
    if "error" not in exif:
        result["recommendations"] = generate_recommendations(exif)

    # Histogram
    if include_histogram:
        try:
            hist_data = await asyncio.to_thread(compute_histogram, path)
            result["histogram"] = {
                "statistics": hist_data["statistics"],
                "clipping": hist_data["clipping"],
                "total_pixels": hist_data["total_pixels"],
                "svg": render_histogram_svg(hist_data),
            }
        except Exception:  # noqa: BLE001
            logger.debug("Histogram failed for %s", path, exc_info=True)

    # Thumbnail
    if include_thumbnail:
        try:
            thumb_bytes = await asyncio.to_thread(generate_thumbnail, path, thumbnail_max_width)
            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(result, indent=2)),
                    MCPImage(data=thumb_bytes, format="jpeg").to_image_content(),
                ],
                structured_content=result,
            )
        except Exception:  # noqa: BLE001
            logger.debug("Thumbnail failed for %s", path, exc_info=True)

    return result


@mcp.tool()
async def interpolate_profiles(
    ctx: Context,
    profile_a: str,
    profile_b: str,
    factor: float = 0.5,
    output_name: str = "interpolated",
    file_path: str | None = None,
    include_preview: bool = False,
    preview_max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Blend two PP3 profiles by linear interpolation.

    Numeric values are interpolated (factor=0.0 gives profile A, factor=1.0
    gives profile B). Non-numeric values are taken from the nearer profile.
    Useful for creating intermediate looks between two processing styles.
    Params: profile_a, profile_b, factor, output_name, file_path,
    include_preview, preview_max_width
    """
    config = get_config(ctx)

    path_a = Path(profile_a)
    path_b = Path(profile_b)

    if not path_a.is_file():
        return {"error": f"Profile A not found: {profile_a}"}
    if not path_b.is_file():
        return {"error": f"Profile B not found: {profile_b}"}

    prof_a = PP3Profile()
    prof_a.load(path_a)
    prof_b = PP3Profile()
    prof_b.load(path_b)

    interpolated = PP3Profile.interpolate(prof_a, prof_b, factor)

    output_path = config.output_dir / f"{output_name}.pp3"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    interpolated.save(output_path)

    result: dict[str, Any] = {
        "profile_a": str(path_a),
        "profile_b": str(path_b),
        "factor": factor,
        "output_path": str(output_path),
        "summary": interpolated.to_dict(),
    }

    if include_preview and file_path:
        rt_check = _require_rt(config)
        if not isinstance(rt_check, dict):
            raw_path = Path(file_path)
            if raw_path.is_file():
                width = preview_max_width
                preview_result = await _render_preview(config, raw_path, interpolated, max_width=width, label="interp")
                result["preview"] = preview_result
                if preview_result.get("success"):
                    try:
                        img_content = await _preview_to_image_content(preview_result["preview_path"], width)
                        return ToolResult(
                            content=[
                                TextContent(type="text", text=json.dumps(result, indent=2)),
                                img_content,
                            ],
                            structured_content=result,
                        )
                    except Exception:  # noqa: BLE001
                        logger.debug("Preview failed for interpolated profile", exc_info=True)

    return result


@mcp.tool()
async def batch_analyze(
    ctx: Context,
    file_paths: list[str],
    max_images: int = 20,
    include_thumbnails: bool = True,
    thumbnail_max_width: int = 200,
) -> dict[str, Any] | ToolResult:
    """Batch analysis of multiple images with EXIF, recommendations, and stats.

    A lightweight alternative to calling analyze_image N times. Returns per-image
    EXIF data, processing recommendations, and summary histogram statistics
    (mean, clipping) without full 256-bin channel data or SVG. Optionally
    includes small thumbnails.
    Params: file_paths, max_images, include_thumbnails, thumbnail_max_width
    """
    capped = file_paths[:max_images]
    analyses: list[dict[str, Any]] = []
    image_contents: list[Any] = []

    for fp in capped:
        path = Path(fp)
        entry: dict[str, Any] = {"file_path": fp}

        if not path.is_file():
            entry["error"] = f"File not found: {fp}"
            analyses.append(entry)
            continue

        # EXIF + recommendations
        exif = read_exif_data(path)
        entry["exif"] = exif
        if "error" not in exif:
            entry["recommendations"] = generate_recommendations(exif)

        # Lightweight histogram stats (no full channel data, no SVG)
        try:
            hist_data = await asyncio.to_thread(compute_histogram, path)
            entry["histogram_summary"] = {
                "statistics": hist_data["statistics"],
                "clipping": hist_data["clipping"],
                "total_pixels": hist_data["total_pixels"],
            }
        except Exception:  # noqa: BLE001
            logger.debug("Histogram failed for %s", fp, exc_info=True)

        analyses.append(entry)

        # Optional small thumbnail
        if include_thumbnails:
            try:
                thumb_bytes = await asyncio.to_thread(generate_thumbnail, path, thumbnail_max_width)
                image_contents.append(MCPImage(data=thumb_bytes, format="jpeg").to_image_content())
            except Exception:  # noqa: BLE001
                logger.debug("Thumbnail failed for %s", fp, exc_info=True)

    metadata: dict[str, Any] = {
        "analyses": analyses,
        "total": len(capped),
        "capped": len(file_paths) > max_images,
    }

    if image_contents:
        try:
            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(metadata, indent=2)),
                    *image_contents,
                ],
                structured_content=metadata,
            )
        except Exception:  # noqa: BLE001
            logger.debug("ToolResult creation failed for batch_analyze", exc_info=True)

    return metadata


# ---------------------------------------------------------------------------
# Locallab — Luminance-based Local Adjustments
# ---------------------------------------------------------------------------


@mcp.tool()
async def add_luminance_adjustment(
    ctx: Context,
    profile_path: str,
    adjustment_type: str,
    parameters: dict[str, Any],
    luminance_range: dict[str, int] | None = None,
    transition: int = 30,
    strength: int = 100,
    spot_name: str | None = None,
    save_as: str | None = None,
) -> dict[str, Any]:
    """Add a luminance-based local adjustment to a PP3 profile.

    Creates a Locallab spot that targets a specific luminance range (shadows,
    midtones, highlights, or custom). The adjustment only affects pixels
    within the specified brightness range, enabling selective edits like
    shadow recovery or highlight compression without affecting the rest.

    adjustment_type: "shadows" (0-30%), "midtones" (25-75%),
    "highlights" (70-100%), or "custom" (requires luminance_range).

    parameters: Processing adjustments to apply in the selected range.
    Keys: exposure (-2 to +2 EV), contrast (-100 to +100),
    saturation (-100 to +100), brightness (-100 to +100), black (0-500),
    highlight_compression (0-500), sharpening (0-100), denoise_luma (0-100),
    denoise_chroma (0-100), white_balance_shift (Kelvin, -500 to +500).

    luminance_range (custom only): {"lower": 0-100, "upper": 0-100,
    "lower_transition": 0-100, "upper_transition": 0-100}.

    Params: profile_path, adjustment_type, parameters, luminance_range,
    transition, strength, spot_name, save_as
    """
    path = Path(profile_path)
    if not path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    profile = PP3Profile()
    profile.load(path)

    try:
        idx = add_spot(
            profile,
            adjustment_type=adjustment_type,
            parameters=parameters,
            luminance_range=luminance_range,
            transition=transition,
            strength=strength,
            spot_name=spot_name,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    out_path = Path(save_as) if save_as else path
    profile.save(out_path)

    spot_info = read_spot(profile, idx)
    return {
        "profile_path": str(out_path),
        "spot_index": idx,
        "spot_name": spot_info["name"] if spot_info else spot_name,
        "adjustment_type": adjustment_type,
        "luminance_range": spot_info.get("luminance_range") if spot_info else None,
        "parameters_applied": parameters,
        "total_spots": get_spot_count(profile),
    }


@mcp.tool()
async def preview_luminance_mask(
    ctx: Context,
    file_path: str,
    profile_path: str,
    spot_index: int = 0,
    max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Preview a luminance mask showing which image areas are affected by a local adjustment.

    Generates a grayscale mask image: white = full effect, black = no effect,
    gray = transition zone. Use this to verify the luminance range targets
    the correct tonal areas before processing.

    Params: file_path, profile_path, spot_index, max_width
    """
    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"Image file not found: {file_path}"}

    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    profile = PP3Profile()
    profile.load(pp3_path)

    spot = read_spot(profile, spot_index)
    if spot is None:
        return {"error": f"Spot index {spot_index} not found (total: {get_spot_count(profile)})"}

    lum_range = spot.get("luminance_range")
    if lum_range is None:
        return {"error": "Could not determine luminance range for this spot"}

    # Generate mask preview using Pillow
    try:
        mask_bytes = await asyncio.to_thread(_generate_mask_preview, raw_path, lum_range, max_width)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Mask preview generation failed", exc_info=True)
        return {"error": f"Failed to generate mask preview: {exc}"}

    metadata: dict[str, Any] = {
        "spot_index": spot_index,
        "spot_name": spot["name"],
        "luminance_range": lum_range,
        "adjustment_type": spot["type"],
    }

    try:
        return ToolResult(
            content=[
                TextContent(type="text", text=json.dumps(metadata, indent=2)),
                MCPImage(data=mask_bytes, format="jpeg").to_image_content(),
            ],
            structured_content=metadata,
        )
    except Exception:  # noqa: BLE001
        logger.debug("ToolResult creation failed for mask preview", exc_info=True)
        return metadata


def _generate_mask_preview(
    image_path: Path,
    lum_range: dict[str, int],
    max_width: int,
) -> bytes:
    """Generate a grayscale luminance mask preview image.

    Args:
        image_path: Path to the source image.
        lum_range: Dict with lower/upper keys (0-100 scale).
        max_width: Maximum output dimension.

    Returns:
        JPEG bytes of the mask image.
    """
    import io

    from PIL import Image, ImageOps

    lower = lum_range.get("lower", 0) / 100.0 * 255.0
    upper = lum_range.get("upper", 100) / 100.0 * 255.0

    with Image.open(image_path) as file_img:
        img: Image.Image = ImageOps.exif_transpose(file_img) or file_img

        # Resize first for performance
        w, h = img.size
        if max(w, h) > max_width:
            scale = max_width / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        # Convert to grayscale (luminance)
        gray = img.convert("L")

        # Build mask: pixels in range -> white, outside -> black
        pixels = list(gray.getdata())
        mask_data = []
        for p in pixels:
            if lower <= p <= upper:
                mask_data.append(255)
            elif p < lower:
                # Transition zone below
                dist = lower - p
                if dist < 30:  # ~12% transition
                    mask_data.append(int(255 * (1.0 - dist / 30.0)))
                else:
                    mask_data.append(0)
            else:
                # Transition zone above
                dist = p - upper
                if dist < 30:
                    mask_data.append(int(255 * (1.0 - dist / 30.0)))
                else:
                    mask_data.append(0)

        mask_img = Image.new("L", gray.size)
        mask_img.putdata(mask_data)

        buf = io.BytesIO()
        mask_img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()


@mcp.tool()
async def list_local_adjustments(
    ctx: Context,
    profile_path: str,
) -> dict[str, Any]:
    """List all Locallab (local adjustment) spots in a PP3 profile.

    Shows each spot's name, type, luminance range, active parameters,
    and enabled state. Use this to inspect the local adjustments before
    previewing or modifying them.

    Params: profile_path
    """
    path = Path(profile_path)
    if not path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    profile = PP3Profile()
    profile.load(path)

    count = get_spot_count(profile)
    spots: list[dict[str, Any]] = []
    for i in range(count):
        spot = read_spot(profile, i)
        if spot is not None:
            spots.append(spot)

    return {
        "profile_path": profile_path,
        "total_spots": count,
        "spots": spots,
    }


@mcp.tool()
async def adjust_local_spot(
    ctx: Context,
    profile_path: str,
    spot_index: int,
    parameters: dict[str, Any] | None = None,
    luminance_range: dict[str, int] | None = None,
    strength: int | None = None,
    enabled: bool | None = None,
    save_as: str | None = None,
) -> dict[str, Any]:
    """Modify parameters of an existing Locallab spot in a PP3 profile.

    Change processing parameters, luminance range, strength, or
    enable/disable a spot without removing and re-adding it.

    Params: profile_path, spot_index, parameters, luminance_range,
    strength, enabled, save_as
    """
    path = Path(profile_path)
    if not path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    profile = PP3Profile()
    profile.load(path)

    if not update_spot(profile, spot_index, parameters, luminance_range, strength, enabled):
        return {"error": f"Spot index {spot_index} not found (total: {get_spot_count(profile)})"}

    out_path = Path(save_as) if save_as else path
    profile.save(out_path)

    spot = read_spot(profile, spot_index)
    return {
        "profile_path": str(out_path),
        "spot_index": spot_index,
        "updated": spot if spot else {},
        "total_spots": get_spot_count(profile),
    }


@mcp.tool()
async def remove_local_adjustment(
    ctx: Context,
    profile_path: str,
    spot_index: int,
    save_as: str | None = None,
) -> dict[str, Any]:
    """Remove a Locallab spot from a PP3 profile.

    Deletes the spot at the given index and re-indexes remaining spots.

    Params: profile_path, spot_index, save_as
    """
    path = Path(profile_path)
    if not path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    profile = PP3Profile()
    profile.load(path)

    old_count = get_spot_count(profile)
    if not remove_spot(profile, spot_index):
        return {"error": f"Spot index {spot_index} not found (total: {old_count})"}

    out_path = Path(save_as) if save_as else path
    profile.save(out_path)

    return {
        "profile_path": str(out_path),
        "removed_index": spot_index,
        "total_spots": get_spot_count(profile),
    }


@mcp.tool()
async def preview_with_adjustments(
    ctx: Context,
    file_path: str,
    profile_path: str,
    max_width: int = 600,
    include_histogram: bool = False,
) -> dict[str, Any] | ToolResult:
    """Preview a RAW file with all active local adjustments applied.

    Renders a preview JPEG using RT CLI with the full profile including
    Locallab spots. Optionally includes histogram statistics for the
    processed result. Use this after add_luminance_adjustment or
    apply_local_preset to verify the effect visually.

    Params: file_path, profile_path, max_width, include_histogram
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"Image file not found: {file_path}"}

    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    # Pass Path to _render_preview to avoid parser crash on Locallab profiles.
    # Load PP3Profile separately only for spot metadata reading.
    profile = PP3Profile()
    profile.load(pp3_path)
    spot_count = get_spot_count(profile)

    preview_result = await _render_preview(config, raw_path, pp3_path, max_width=max_width, label="localadj")

    if not preview_result.get("success"):
        return preview_result

    preview_path = preview_result["preview_path"]

    # Build metadata
    spots_summary: list[dict[str, Any]] = []
    for i in range(spot_count):
        spot = read_spot(profile, i)
        if spot:
            spots_summary.append(
                {
                    "index": spot["index"],
                    "name": spot["name"],
                    "type": spot["type"],
                    "enabled": spot["enabled"],
                }
            )

    metadata: dict[str, Any] = {
        "success": True,
        "preview_path": preview_path,
        "active_spots": spot_count,
        "spots": spots_summary,
    }

    # Optional histogram
    if include_histogram:
        try:
            hist_data = await asyncio.to_thread(compute_histogram, Path(preview_path))
            metadata["histogram"] = {
                "statistics": hist_data["statistics"],
                "clipping": hist_data["clipping"],
            }
        except Exception:  # noqa: BLE001
            logger.debug("Histogram failed for preview", exc_info=True)

    # Thumbnail for inline display
    try:
        thumb = await _preview_to_image_content(preview_path, max_width)
        return ToolResult(
            content=[
                TextContent(type="text", text=json.dumps(metadata, indent=2)),
                thumb,
            ],
            structured_content=metadata,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Thumbnail creation failed for preview_with_adjustments", exc_info=True)
        return metadata


@mcp.tool()
async def apply_local_preset(
    ctx: Context,
    profile_path: str,
    preset: str,
    intensity: int = 50,
    save_as: str | None = None,
) -> dict[str, Any]:
    """Apply a predefined local adjustment preset to a PP3 profile.

    Available presets: shadow_recovery, highlight_protection,
    split_tone_warm_cool, midtone_contrast, shadow_desaturation,
    amoled_optimize, hdr_natural.

    intensity scales all parameters: 50 = default, 25 = half, 100 = double.

    Params: profile_path, preset, intensity, save_as
    """
    path = Path(profile_path)
    if not path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    profile = PP3Profile()
    profile.load(path)

    preset_info = get_local_preset(preset)
    if preset_info is None:
        available = list_local_presets()
        return {
            "error": f"Unknown preset: {preset!r}",
            "available_presets": available,
        }

    try:
        indices = apply_preset(profile, preset, intensity)
    except ValueError as exc:
        return {"error": str(exc)}

    out_path = Path(save_as) if save_as else path
    profile.save(out_path)

    # Read back the spots we just added
    spots: list[dict[str, Any]] = []
    for idx in indices:
        spot = read_spot(profile, idx)
        if spot:
            spots.append(spot)

    return {
        "profile_path": str(out_path),
        "preset": preset,
        "description": preset_info["description"],
        "intensity": intensity,
        "spots_added": spots,
        "total_spots": get_spot_count(profile),
    }


# ---------------------------------------------------------------------------
# Feature A — Lens Correction
# ---------------------------------------------------------------------------


@mcp.tool()
async def apply_lens_correction(
    ctx: Context,
    profile_path: str,
    mode: str = "auto",
    lcp_file: str | None = None,
    correct_distortion: bool = True,
    correct_vignetting: bool = True,
    correct_ca: bool = False,
    file_path: str | None = None,
    save_as: str | None = None,
) -> dict[str, Any]:
    """Apply Lensfun or Adobe LCP lens correction to a PP3 profile.

    Writes LensProfile section into the profile. Use mode='auto' for automatic
    Lensfun correction (camera/lens detected from RAW EXIF), or mode='lcp' to
    specify an Adobe Lens Correction Profile (.lcp file).
    Params: profile_path, mode ('auto'|'lcp'), lcp_file, correct_distortion,
    correct_vignetting, correct_ca, file_path (optional RAW for EXIF info), save_as
    """
    config = get_config(ctx)

    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    if mode not in ("auto", "lcp"):
        return {"error": f"Invalid mode '{mode}'. Use 'auto' or 'lcp'."}

    if mode == "lcp":
        if not lcp_file:
            return {"error": "mode='lcp' requires lcp_file parameter."}
        lcp_path = Path(lcp_file)
        if not lcp_path.is_absolute() and config.lcp_dir:
            lcp_path = config.lcp_dir / lcp_path
        if not lcp_path.is_file():
            return {"error": f"LCP file not found: {lcp_path}", "suggestion": "Set RT_LCP_DIR or use an absolute path."}

    profile = PP3Profile()
    profile.load(pp3_path)

    if mode == "auto":
        profile.set("LensProfile", "LcMode", "lfauto")
    else:
        profile.set("LensProfile", "LcMode", "lcp")
        profile.set("LensProfile", "LCPFile", str(lcp_path).replace("\\", "\\\\"))

    profile.set("LensProfile", "UseDistortion", str(correct_distortion).lower())
    profile.set("LensProfile", "UseVignette", str(correct_vignetting).lower())
    profile.set("LensProfile", "UseCA", str(correct_ca).lower())

    out_path = Path(save_as) if save_as else pp3_path
    profile.save(out_path)

    result: dict[str, Any] = {
        "profile_path": str(out_path),
        "mode": mode,
        "corrections_enabled": {
            "distortion": correct_distortion,
            "vignetting": correct_vignetting,
            "chromatic_aberration": correct_ca,
        },
    }

    if file_path:
        raw_path = Path(file_path)
        if raw_path.is_file():
            exif = read_exif_data(raw_path)
            result["camera_detected"] = exif.get("camera_model") or exif.get("camera_make")
            result["lens_detected"] = exif.get("lens_model")
        else:
            result["warning"] = f"file_path not found for EXIF read: {file_path}"

    if mode == "lcp":
        result["lcp_file"] = str(lcp_path)

    return result


@mcp.tool()
async def check_lens_support(
    ctx: Context,
    file_path: str | None = None,
    camera_make: str | None = None,
    camera_model: str | None = None,
    lens_model: str | None = None,
) -> dict[str, Any]:
    """Check whether a camera/lens combination has a Lensfun calibration profile.

    Reads EXIF from a RAW file to detect camera/lens automatically, or accepts
    manual camera_make, camera_model, lens_model parameters. Parses the local
    Lensfun XML database (configured via RT_LENSFUN_DIR or auto-detected).
    Params: file_path (optional RAW for EXIF detection), camera_make, camera_model, lens_model
    """
    config = get_config(ctx)

    if config.lensfun_dir is None:
        return {
            "error": "Lensfun database directory not found.",
            "suggestion": "Set RT_LENSFUN_DIR to the directory containing Lensfun XML files.",
        }

    make = camera_make
    model = camera_model
    lens = lens_model

    if file_path:
        raw_path = Path(file_path)
        if raw_path.is_file():
            exif = read_exif_data(raw_path)
            make = make or exif.get("camera_make")
            model = model or exif.get("camera_model")
            lens = lens or exif.get("lens_model")

    return _check_lens_support(
        lensfun_dir=config.lensfun_dir,
        camera_make=make,
        camera_model=model,
        lens_model=lens,
    )


# ---------------------------------------------------------------------------
# Feature B — LUT Support
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_luts(
    ctx: Context,
    directory: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """List available HaldCLUT film simulation LUT files.

    Scans RT_HALDCLUT_DIR (or the optional directory parameter) for PNG/TIFF
    HaldCLUT files and groups them by subdirectory category (e.g. 'Fuji', 'Kodak').
    Params: directory (optional override), category (optional filter e.g. 'Fuji')
    """
    config = get_config(ctx)

    base: Path | None
    if directory:
        base = Path(directory)
        if not base.is_dir():
            return {"error": f"Directory not found: {directory}"}
    elif config.haldclut_dir:
        base = config.haldclut_dir
    else:
        return {
            "error": "HaldCLUT directory not configured.",
            "suggestion": "Set RT_HALDCLUT_DIR or pass directory=... to this tool.",
        }

    categories: dict[str, list[str]] = {}
    for lut_file in sorted(base.rglob("*")):
        if lut_file.suffix.lower() not in (".png", ".tif", ".tiff"):
            continue
        if not lut_file.is_file():
            continue
        rel = lut_file.relative_to(base)
        parts = rel.parts
        cat = parts[0] if len(parts) > 1 else ""
        if category and cat.lower() != category.lower():
            continue
        categories.setdefault(cat, []).append(str(rel))

    grouped = {cat: {"count": len(files), "luts": files} for cat, files in sorted(categories.items())}
    total = sum(len(cast(list[str], v["luts"])) for v in grouped.values())

    return {
        "haldclut_directory": str(base),
        "total": total,
        "categories": grouped,
    }


@mcp.tool()
async def apply_lut(
    ctx: Context,
    profile_path: str,
    lut_name: str,
    strength: int = 100,
    save_as: str | None = None,
) -> dict[str, Any]:
    """Apply a HaldCLUT film simulation LUT to a PP3 profile.

    Writes the [Film Simulation] section into the profile. lut_name is the
    relative path from RT_HALDCLUT_DIR, e.g. 'Fuji/Fuji Velvia 50.png'.
    strength controls blend intensity (0-100).
    Params: profile_path, lut_name, strength (0-100), save_as
    """
    config = get_config(ctx)

    pp3_path = Path(profile_path)
    if not pp3_path.is_file():
        return {"error": f"Profile not found: {profile_path}"}

    if not 0 <= strength <= 100:
        return {"error": f"strength must be 0-100 (got {strength})."}

    profile = PP3Profile()
    profile.load(pp3_path)

    profile.set("Film Simulation", "Enabled", "true")
    profile.set("Film Simulation", "ClutFilename", lut_name)
    profile.set("Film Simulation", "Strength", str(strength))

    out_path = Path(save_as) if save_as else pp3_path
    profile.save(out_path)

    result: dict[str, Any] = {
        "profile_path": str(out_path),
        "lut_name": lut_name,
        "strength": strength,
    }

    if config.haldclut_dir:
        lut_abs = config.haldclut_dir / lut_name
        if not lut_abs.is_file():
            result["warning"] = f"LUT file not found at {lut_abs}. Verify RT_HALDCLUT_DIR and the HaldCLUT collection."

    return result


@mcp.tool()
async def preview_lut(
    ctx: Context,
    file_path: str,
    lut_name: str,
    base_profile: str | None = None,
    strength: int = 100,
    max_width: int = 600,
) -> dict[str, Any] | ToolResult:
    """Render an inline preview of a RAW file with a HaldCLUT film simulation applied.

    Optionally merges onto an existing PP3 base_profile so WB, exposure, etc.
    are preserved. Returns an inline thumbnail image.
    Params: file_path, lut_name, base_profile (optional PP3 path), strength (0-100), max_width
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}

    if not 0 <= strength <= 100:
        return {"error": f"strength must be 0-100 (got {strength})."}

    if base_profile:
        base_path = Path(base_profile)
        if not base_path.is_file():
            return {"error": f"Base profile not found: {base_profile}"}
        profile = PP3Profile()
        profile.load(base_path)
    else:
        from rawtherapee_mcp.pp3_generator import create_neutral_profile

        profile = create_neutral_profile()

    profile.set("Film Simulation", "Enabled", "true")
    profile.set("Film Simulation", "ClutFilename", lut_name)
    profile.set("Film Simulation", "Strength", str(strength))

    preview_result = await _render_preview(config, raw_path, profile, max_width=max_width, label="lut_preview")
    if not preview_result.get("success"):
        return preview_result

    text_summary = json.dumps(
        {"lut_name": lut_name, "strength": strength, "base_profile": base_profile},
        indent=2,
    )
    try:
        image_content = await _preview_to_image_content(preview_result["preview_path"], max_width)
        return ToolResult(
            content=[TextContent(type="text", text=text_summary), image_content],
            structured_content=preview_result,
        )
    except Exception:  # noqa: BLE001
        logger.debug("LUT preview thumbnail failed", exc_info=True)
        return preview_result


@mcp.tool()
async def preview_lut_comparison(
    ctx: Context,
    file_path: str,
    lut_names: list[str],
    base_profile: str | None = None,
    strength: int = 100,
    max_width: int = 300,
) -> dict[str, Any] | ToolResult:
    """Render side-by-side inline previews for 2-5 HaldCLUT LUTs for quick comparison.

    Renders each LUT sequentially and returns all thumbnails in a single response.
    Each image is labeled with its LUT name. Typical render time: 2-5s per LUT.
    Params: file_path, lut_names (list of 2-5 LUT relative paths), base_profile,
    strength (0-100), max_width (per image)
    """
    config = get_config(ctx)
    rt_check = _require_rt(config)
    if isinstance(rt_check, dict):
        return rt_check

    if not 2 <= len(lut_names) <= 5:
        return {"error": f"lut_names must contain 2-5 entries (got {len(lut_names)})."}

    raw_path = Path(file_path)
    if not raw_path.is_file():
        return {"error": f"RAW file not found: {file_path}"}

    if not 0 <= strength <= 100:
        return {"error": f"strength must be 0-100 (got {strength})."}

    base_pp3: PP3Profile | None = None
    if base_profile:
        base_path = Path(base_profile)
        if not base_path.is_file():
            return {"error": f"Base profile not found: {base_profile}"}
        base_pp3 = PP3Profile()
        base_pp3.load(base_path)

    content: list[TextContent | ImageContent] = []
    errors: list[dict[str, str]] = []

    header = f"LUT comparison — strength={strength}" + (f" — base: {base_profile}" if base_profile else "")
    content.append(TextContent(type="text", text=header))

    for lut_name in lut_names:
        if base_pp3 is not None:
            profile = base_pp3.copy()
        else:
            from rawtherapee_mcp.pp3_generator import create_neutral_profile

            profile = create_neutral_profile()

        profile.set("Film Simulation", "Enabled", "true")
        profile.set("Film Simulation", "ClutFilename", lut_name)
        profile.set("Film Simulation", "Strength", str(strength))

        preview_result = await _render_preview(config, raw_path, profile, max_width=max_width, label="lutcmp")

        if not preview_result.get("success"):
            errors.append({"lut_name": lut_name, "error": preview_result.get("error", "render failed")})
            content.append(TextContent(type="text", text=f"[ERROR] {lut_name}: {preview_result.get('error')}"))
            continue

        content.append(TextContent(type="text", text=lut_name))
        try:
            image_content = await _preview_to_image_content(preview_result["preview_path"], max_width)
            content.append(image_content)
        except Exception:  # noqa: BLE001
            logger.debug("LUT comparison thumbnail failed for %s", lut_name, exc_info=True)
            errors.append({"lut_name": lut_name, "error": "thumbnail generation failed"})

    structured: dict[str, Any] = {
        "lut_names": lut_names,
        "strength": strength,
        "base_profile": base_profile,
        "errors": errors,
    }

    return ToolResult(content=content, structured_content=structured)


# ---------------------------------------------------------------------------
# Feature C — Profile Inheritance
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_profile_variant(
    ctx: Context,
    parent_profile: str,
    variant_name: str,
    overrides: dict[str, Any],
    description: str | None = None,
) -> dict[str, Any]:
    """Create a child PP3 profile variant derived from a parent template.

    The variant is generated by merging the parent PP3 with the given overrides
    (raw PP3 section -> key -> value dict). A single merged PP3 is written to
    _generated/<variant_name>.pp3. The parent-child relationship is tracked in
    profile_hierarchy.json for update propagation.
    Params: parent_profile (template name or path), variant_name, overrides
    (e.g. {'White Balance': {'Temperature': '3800'}}), description
    """
    config = get_config(ctx)
    templates_dir = _get_templates_dir()

    # Resolve parent PP3 path
    if Path(parent_profile).is_file():
        parent_pp3_path = Path(parent_profile).resolve()
    else:
        try:
            parent_pp3_obj = _load_template(parent_profile, templates_dir, config.custom_templates_dir)
            # Determine which path was actually loaded
            custom_p = config.custom_templates_dir / f"{parent_profile}.pp3"
            if custom_p.is_file():
                parent_pp3_path = custom_p.resolve()
            else:
                builtin_p = templates_dir / f"{parent_profile}.pp3"
                parent_pp3_path = builtin_p.resolve()
            del parent_pp3_obj
        except FileNotFoundError:
            return {"error": f"Parent profile not found: {parent_profile}"}

    # Validate variant name doesn't clash with real templates
    conflict = config.custom_templates_dir / f"{variant_name}.pp3"
    if conflict.is_file():
        return {"error": f"A template named '{variant_name}' already exists. Choose a different variant_name."}

    try:
        return _create_variant(
            custom_templates_dir=config.custom_templates_dir,
            parent_pp3_path=parent_pp3_path,
            variant_name=variant_name,
            overrides=overrides,
            description=description,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Failed to create variant: {exc}"}


@mcp.tool()
async def list_profile_variants(
    ctx: Context,
    parent_profile: str | None = None,
) -> dict[str, Any]:
    """List profile variants tracked by the inheritance system.

    Shows parent -> [variants] relationships with override summaries and
    effective PP3 paths. Optionally filter by parent_profile name.
    Params: parent_profile (optional filter)
    """
    config = get_config(ctx)
    return _list_variants(config.custom_templates_dir, parent_profile)


@mcp.tool()
async def update_base_profile(
    ctx: Context,
    profile_name: str,
    adjustments: dict[str, Any],
    propagate: bool = True,
) -> dict[str, Any]:
    """Update a base PP3 template and optionally propagate changes to all its variants.

    Applies adjustments (raw PP3 section -> {key: value} dict, same format as
    adjust_profile) to the named template, then regenerates all child variants so
    their override-specific settings are preserved on top of the updated base.
    Params: profile_name (template name or path), adjustments, propagate (default True)
    """
    config = get_config(ctx)
    templates_dir = _get_templates_dir()

    # Resolve the PP3 file for the named profile (custom only — built-ins are read-only)
    if Path(profile_name).is_file():
        pp3_path = Path(profile_name).resolve()
    else:
        custom_p = config.custom_templates_dir / f"{profile_name}.pp3"
        if not custom_p.is_file():
            # Check if it's a built-in
            builtin_p = templates_dir / f"{profile_name}.pp3"
            if builtin_p.is_file():
                return {
                    "error": f"'{profile_name}' is a built-in template and cannot be modified.",
                    "suggestion": "Use save_template to create a custom copy first.",
                }
            return {"error": f"Profile not found: {profile_name}"}
        pp3_path = custom_p.resolve()

    profile = PP3Profile()
    profile.load(pp3_path)
    apply_parameters(profile, adjustments, raw_fallback=True)
    profile.save(pp3_path)

    result: dict[str, Any] = {
        "profile_name": profile_name,
        "profile_path": str(pp3_path),
        "adjustments_applied": adjustments,
    }

    if propagate:
        parent_name = pp3_path.stem
        propagation = _propagate_to_variants(config.custom_templates_dir, parent_name, pp3_path)
        result["variants_updated"] = propagation
    else:
        result["variants_updated"] = []

    return result


# ---------------------------------------------------------------------------
# Feature D — Metadata Privacy
# ---------------------------------------------------------------------------


@mcp.tool()
async def inspect_metadata(
    ctx: Context,
    file_path: str,
) -> dict[str, Any]:
    """Inspect EXIF metadata in an exported JPEG/TIFF and classify by sensitivity.

    Returns sensitive fields (GPS, serial numbers, owner), technical fields
    (camera, lens, ISO, aperture, shutter), processing info (software), rights
    (copyright, artist), and privacy recommendations for public sharing.
    Params: file_path (exported JPEG or TIFF)
    """
    path = Path(file_path)
    if not path.is_file():
        return {"error": f"File not found: {file_path}"}

    return await asyncio.to_thread(_inspect_metadata, path)


@mcp.tool()
async def strip_metadata(
    ctx: Context,
    file_path: str,
    strip_gps: bool = True,
    strip_camera_serial: bool = True,
    strip_lens_serial: bool = True,
    strip_software: bool = False,
    strip_owner: bool = False,
    strip_all: bool = False,
    keep_copyright: bool = True,
    keep_orientation: bool = True,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Strip selected EXIF metadata from an exported JPEG file.

    Operates losslessly — only the EXIF APP1 segment is rewritten, the JPEG
    image data is not recompressed. By default removes GPS and serial numbers.
    Use strip_all=True to remove everything except orientation (and copyright
    if keep_copyright=True).
    Params: file_path, strip_gps, strip_camera_serial, strip_lens_serial,
    strip_software, strip_owner, strip_all, keep_copyright, keep_orientation,
    output_path (None = in-place)
    """
    path = Path(file_path)
    if not path.is_file():
        return {"error": f"File not found: {file_path}"}

    out = Path(output_path) if output_path else path

    try:
        return await asyncio.to_thread(
            _strip_metadata,
            path,
            out,
            strip_gps=strip_gps,
            strip_camera_serial=strip_camera_serial,
            strip_lens_serial=strip_lens_serial,
            strip_software=strip_software,
            strip_owner=strip_owner,
            strip_all=strip_all,
            keep_copyright=keep_copyright,
            keep_orientation=keep_orientation,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"Failed to strip metadata: {exc}",
            "suggestion": "Ensure the file is a valid JPEG with EXIF data.",
        }


@mcp.tool()
async def set_metadata(
    ctx: Context,
    file_path: str,
    copyright: str | None = None,
    artist: str | None = None,
    description: str | None = None,
    keywords: list[str] | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Write copyright, artist, description, and keywords into an exported JPEG file.

    Writes metadata losslessly (EXIF APP1 segment only, no JPEG recompression).
    Keywords are stored as XPKeywords (UTF-16LE, semicolon-separated) for
    compatibility with Windows Explorer and most DAM software.
    Params: file_path, copyright (e.g. '© 2026 Luca Marien'), artist, description,
    keywords (list of strings), output_path (None = in-place)
    """
    path = Path(file_path)
    if not path.is_file():
        return {"error": f"File not found: {file_path}"}

    if not any([copyright, artist, description, keywords]):
        return {"error": "At least one of copyright, artist, description, or keywords must be provided."}

    out = Path(output_path) if output_path else path

    try:
        return await asyncio.to_thread(
            _set_metadata,
            path,
            out,
            copyright=copyright,
            artist=artist,
            description=description,
            keywords=keywords,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"Failed to set metadata: {exc}",
            "suggestion": "Ensure the file is a valid JPEG with EXIF data.",
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the RawTherapee MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
