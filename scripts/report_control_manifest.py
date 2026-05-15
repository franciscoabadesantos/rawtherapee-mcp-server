"""Print a compact audit report for the control manifest."""

from __future__ import annotations

from rawtherapee_mcp.control_policy import build_manifest_report


def _print_list(title: str, items: list[str]) -> None:
    print(f"{title} ({len(items)}):")
    for item in items:
        print(f"- {item}")
    if not items:
        print("- <none>")
    print()


def main() -> int:
    report = build_manifest_report()
    versions = report.get("rawtherapee_versions", {})
    default_policy = report.get("unknown_default_policy", {})

    print("RawTherapee Control Manifest Report")
    print("==================================")
    print(f"rawtherapee_versions: {versions}")
    print(f"unknown/manual-only default policy: {default_policy}")
    print()

    allowed = report.get("allowed_autonomous_controls", [])
    blocked = report.get("blocked_controls", [])
    pending = report.get("pending_evidence_controls", [])
    approved = report.get("approved_curve_values", {})

    _print_list("allowed autonomous controls", allowed if isinstance(allowed, list) else [])
    _print_list("blocked controls", blocked if isinstance(blocked, list) else [])
    _print_list("pending_evidence controls", pending if isinstance(pending, list) else [])

    print("approved curve values:")
    if isinstance(approved, dict) and approved:
        for control_id in sorted(approved):
            values = approved[control_id]
            print(f"- {control_id}: {values}")
    else:
        print("- <none>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
