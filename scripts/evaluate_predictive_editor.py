"""CLI entrypoint for predictive editor evaluation runs."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from rawtherapee_mcp.evaluation import run_predictive_evaluation


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate auto_edit_predictive on one image.")
    parser.add_argument("--raw", required=True, help="Path to RAW/image input")
    parser.add_argument("--brief", required=True, help="Editing brief")
    parser.add_argument("--intensity", default="medium", help="low|medium|high")
    parser.add_argument("--style", default=None, help="Optional style override")
    parser.add_argument("--preview-width", type=int, default=1024, help="Preview width")
    parser.add_argument("--export", action="store_true", help="Request export through gate")
    parser.add_argument(
        "--prepare-mode",
        default="deterministic",
        choices=["deterministic", "manifest_select"],
        help="Prepare path to evaluate",
    )
    parser.add_argument(
        "--edit-plan-file",
        default=None,
        help="JSON file containing a manifest-select edit plan",
    )
    parser.add_argument(
        "--output-root",
        default="docs/evaluations/runs",
        help="Output directory root for evaluation artifacts",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = asyncio.run(
        run_predictive_evaluation(
            raw_path=args.raw,
            brief=args.brief,
            intensity=args.intensity,
            style=args.style,
            preview_width=args.preview_width,
            export=bool(args.export),
            output_root=Path(args.output_root),
            prepare_mode=args.prepare_mode,
            edit_plan=(
                json.loads(Path(args.edit_plan_file).read_text(encoding="utf-8"))
                if args.edit_plan_file
                else None
            ),
        )
    )
    print(json.dumps(report, indent=2))
    return 1 if "error" in report else 0


if __name__ == "__main__":
    raise SystemExit(main())
