from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "reports" / "json"
OUTPUT_CSV = ROOT / "reports" / "csv"

EXPLANATIONS = {
    "TC02": "DOM can resolve the visible label's for/ID relationship; the Accessibility Tree exposes only the resulting computed name and may not establish the persistent visible relationship.",
    "TC03": "DOM evidence exposes the native element and sequential-Tab focus state; Accessibility Tree evidence exposes computed role/name and focus state. Enter/Space activation is tested only after Tab reaches the control.",
    "TC05": "DOM evidence can identify aria-hidden ancestry. Chromium's Accessibility Tree may omit that ancestry or expose a currently focused descendant, so tree-only evidence can be insufficient.",
    "TC07": "DOM evidence reads explicit live-region attributes; Accessibility Tree evidence reports computed status semantics. Unrelated page-level status nodes must not be mistaken for the message under test.",
    "TC09": "DOM evidence reads aria-selected; Accessibility Tree evidence reports the computed selected state after interaction.",
    "TC10": "DOM evidence reads the title element; Accessibility Tree evidence reads Chromium's computed root web-area name.",
    "TC11": "DOM evidence reads document.activeElement; Accessibility Tree evidence reads its focused-node state. Browser tree snapshots may omit useful focus information.",
    "TC12": "DOM evidence reads dialog state and activeElement; Accessibility Tree evidence reads computed dialog/modal semantics and focused nodes.",
    "TC13": "A screenshot and computed styles are needed to judge a rendered focus indicator; neither structural engine evaluates rendered pixels.",
    "TC14": "A screenshot and rendered foreground/background colors are needed to assess contrast; neither structural engine calculates rendered contrast.",
}


def _difference_type(dom_verdict: str, ax_verdict: str) -> str:
    """verdict_conflict = both engines decided but differently; coverage_gap = one engine could not decide."""
    decided = {"PASS", "FAIL"}
    if dom_verdict in decided and ax_verdict in decided:
        return "verdict_conflict"
    return "coverage_gap"


def _majority(rows: list[dict[str, Any]]) -> str:
    counts = Counter(row["verdict"] for row in rows if row["verdict"] in {"PASS", "FAIL"})
    if not counts:
        return "NOT_TESTABLE"
    highest = max(counts.values())
    leaders = [verdict for verdict, count in counts.items() if count == highest]
    return leaders[0] if len(leaders) == 1 else "UNSTABLE"


def _access_method(row: dict[str, Any]) -> str:
    return row.get("access_method") or (row.get("metadata") or {}).get(
        "access_method", "unspecified"
    )


def compare(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in bundle["results"]:
        grouped[
            (
                row["test_case"],
                row["variant"],
                row["engine"],
                _access_method(row),
            )
        ].append(row)

    disagreements = []
    conditions = sorted(
        {(case, variant, method) for case, variant, _, method in grouped}
    )
    for test_case, variant, access_method in conditions:
        dom_rows = grouped.get((test_case, variant, "DOM", access_method), [])
        ax_rows = grouped.get((test_case, variant, "AX", access_method), [])
        if not dom_rows or not ax_rows:
            continue
        dom_verdict = _majority(dom_rows)
        ax_verdict = _majority(ax_rows)
        dom = dom_rows[-1]
        ax = ax_rows[-1]
        if dom_verdict != ax_verdict:
            disagreements.append(
                {
                "test_case": test_case,
                "variant": variant,
                "access_method": access_method,
                "assertion": "primary",
                "type": _difference_type(dom_verdict, ax_verdict),
                "dom_verdict": dom_verdict,
                "ax_verdict": ax_verdict,
                "dom_rule": dom["rule"],
                "dom_evidence": dom["evidence"],
                "ax_rule": ax["rule"],
                "ax_evidence": ax["evidence"],
                "dom_snapshot": dom["metadata"]["dom_evidence"],
                "ax_snapshot": ax["metadata"]["ax_evidence"],
                "screenshot": dom["metadata"].get("screenshot"),
                "information_source_hypothesis": EXPLANATIONS.get(
                    test_case,
                    "The engines used different evidence representations; inspect the linked snapshots before attributing the disagreement.",
                ),
                "review_status": "pending_manual_adjudication",
                }
            )
        dom_checks = {check["assertion"]: check for check in dom.get("sub_checks", [])}
        ax_checks = {check["assertion"]: check for check in ax.get("sub_checks", [])}
        for assertion in sorted(set(dom_checks) | set(ax_checks)):
            dom_check = dom_checks.get(assertion, {"verdict": "NOT_TESTABLE", "rule": "unsupported", "evidence": "No DOM sub-check."})
            ax_check = ax_checks.get(assertion, {"verdict": "NOT_TESTABLE", "rule": "unsupported", "evidence": "No AX sub-check."})
            if dom_check["verdict"] == ax_check["verdict"]:
                continue
            disagreements.append(
                {
                    "test_case": test_case,
                    "variant": variant,
                    "access_method": access_method,
                    "assertion": assertion,
                    "type": _difference_type(dom_check["verdict"], ax_check["verdict"]),
                    "dom_verdict": dom_check["verdict"],
                    "ax_verdict": ax_check["verdict"],
                    "dom_rule": dom_check["rule"],
                    "dom_evidence": dom_check["evidence"],
                    "ax_rule": ax_check["rule"],
                    "ax_evidence": ax_check["evidence"],
                    "dom_snapshot": dom["metadata"]["dom_evidence"],
                    "ax_snapshot": ax["metadata"]["ax_evidence"],
                    "screenshot": dom["metadata"].get("screenshot"),
                    "information_source_hypothesis": EXPLANATIONS.get(
                        test_case,
                        "The engines used different evidence representations; inspect the linked snapshots before attributing the disagreement.",
                    ),
                    "review_status": "pending_manual_adjudication",
                }
            )
    return disagreements


def analyze_file(input_path: Path) -> tuple[Path, Path, Path]:
    bundle = json.loads(input_path.read_text(encoding="utf-8"))
    disagreements = compare(bundle)
    run_id = bundle["execution_metadata"]["run_id"]
    OUTPUT_JSON.mkdir(parents=True, exist_ok=True)
    OUTPUT_CSV.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_JSON / f"disagreements_{run_id}.json"
    csv_path = OUTPUT_CSV / f"disagreements_{run_id}.csv"
    report_path = ROOT / "reports" / f"disagreements_{run_id}.md"
    json_path.write_text(json.dumps(disagreements, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        fields = [
            "test_case", "variant", "access_method", "dom_verdict", "ax_verdict", "dom_rule",
            "assertion", "type",
            "dom_evidence", "ax_rule", "ax_evidence", "dom_snapshot",
            "ax_snapshot", "screenshot", "information_source_hypothesis",
            "review_status",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(disagreements)

    lines = [
        "# Engine disagreement review",
        "",
        f"Run: `{run_id}`. These are evidence-linked review prompts, not final causal findings.",
        "",
    ]
    if not disagreements:
        lines.extend(["No verdict differences were recorded in this run.", ""])
    for item in disagreements:
        lines.extend(
            [
                f"## {item['test_case']} — {item['variant']} — {item['access_method']}",
                "",
                f"- Assertion: `{item['assertion']}`; difference type: `{item['type']}`",
                f"- DOM: **{item['dom_verdict']}** — `{item['dom_rule']}`: {item['dom_evidence']}",
                f"- AX: **{item['ax_verdict']}** — `{item['ax_rule']}`: {item['ax_evidence']}",
                f"- Hypothesis to verify: {item['information_source_hypothesis']}",
                f"- DOM evidence: `{item['dom_snapshot']}`",
                f"- AX evidence: `{item['ax_snapshot']}`",
                f"- Review status: `{item['review_status']}`",
                "",
            ]
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, csv_path, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create evidence-linked DOM/AX disagreement records.")
    parser.add_argument("input", type=Path, help="Raw experiment result JSON.")
    args = parser.parse_args()
    for path in analyze_file(args.input):
        print(path)


if __name__ == "__main__":
    main()
