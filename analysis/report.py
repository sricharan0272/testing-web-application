from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _format(value: Any) -> str:
    return "Not estimable" if value is None else f"{value:.3f}"


def _with_ci(value: Any, interval: Any) -> str:
    if value is None:
        return "Not estimable"
    if not interval:
        return f"{value:.3f}"
    return f"{value:.3f} [{interval[0]:.2f}, {interval[1]:.2f}]"


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def create_report(experiment_path: Path, analysis_path: Path, disagreement_path: Path) -> Path:
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    disagreements = json.loads(disagreement_path.read_text(encoding="utf-8"))
    dom = analysis["classification_by_engine"]["DOM"]
    ax = analysis["classification_by_engine"]["AX"]
    dom_secondary = analysis["secondary_assertion_classification"]["DOM"]
    ax_secondary = analysis["secondary_assertion_classification"]["AX"]
    all_agreement = analysis["agreement"]["all_classifiable_variants"]
    mapped_agreement = analysis["agreement"]["confirmed_mapping_reference_variants"]
    mcnemar = analysis["mcnemar_exact"]
    types = analysis["disagreement_types"]
    separate = analysis["interpretive_and_extension_cases"]
    repeatability = analysis["repeatability"]["summary"]
    unstable_variants = [
        row
        for row in analysis["repeatability"]["variants"]
        if row["known_runs"] > 0 and not row["stable"]
    ]
    output = ROOT / "reports" / "research_report.md"

    lines = [
        "# DOM-Based and Accessibility-Tree-Based Accessibility Testing",
        "",
        "## Executive summary",
        "",
        "This report describes a controlled SPA test bed with 14 test cases and 28 paired variants. "
        "It compares independently implemented rules over rendered DOM evidence and Chromium's "
        "`Accessibility.getFullAXTree` evidence.",
        "",
        f"**Evidence status:** `{experiment['study_mode']}`. "
        "The expected outcomes are provisional; independent manual, keyboard-only, and screen-reader "
        "validation is still pending. Numeric correctness measures below are therefore reference "
        "comparisons, not validated conformance accuracy.",
        "",
        "## Research question",
        "",
        "Do DOM-based and Accessibility-Tree-based automated testing approaches produce different "
        "results when applied to the same SPA content and test conditions?",
        "",
        "## Method",
        "",
        f"- Test cases: {len(json.loads((ROOT / 'testcases' / 'catalogue.json').read_text(encoding='utf-8'))['test_cases'])}.",
        f"- Variants: {experiment['variant_count']} ({experiment['runs_per_variant']} repeat(s) per variant).",
        f"- Engine outputs: {experiment['result_count']} individual results ({experiment['result_count'] // 2} DOM/AX pairs).",
        "- Browser: Chromium via Playwright for Python; the AX engine reads CDP Accessibility Tree nodes only.",
        "- The DOM engine reads rendered DOM snapshots and DOM-derived interaction/style evidence only.",
        f"- Environment: Python {experiment['execution_metadata']['python_version']}, "
        f"Playwright {experiment['execution_metadata']['playwright_version']}, Chromium "
        f"{experiment['execution_metadata']['chromium_version']}; "
        f"locale {experiment['execution_metadata']['locale']}, viewport "
        f"{experiment['execution_metadata']['viewport']['width']}x"
        f"{experiment['execution_metadata']['viewport']['height']}.",
        "- Raw evidence, execution metadata, JSON, and flattened CSV are retained under `reports/`.",
        "- The statistical unit is a test variant. Repeats contribute to stability, not sample size.",
        "",
        "## Results",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| Classifiable engine pairs (both engines PASS/FAIL, all cases) | {all_agreement['sample_size']} |",
        f"| Agreement rate (all classifiable pairs) | {_format(all_agreement['agreement_rate'])} |",
        f"| Cohen's kappa (all classifiable pairs) | {_format(all_agreement['cohens_kappa'])} |",
        f"| Classifiable pairs on the confirmed-mapping subset | {mapped_agreement['sample_size']} |",
        f"| Kappa on the confirmed-mapping subset | {_format(mapped_agreement['cohens_kappa'])} |",
        f"| Verdict conflicts (one engine PASS, the other FAIL) | {len(types['verdict_conflicts'])} |",
        f"| Coverage gaps (one engine NOT_TESTABLE) | {len(types['coverage_gaps_one_engine_not_testable'])} |",
        f"| Variants neither engine can classify | {len(types['both_not_testable'])} |",
        f"| Exact McNemar discordant pairs (DOM only / AX only correct) | {mcnemar['discordant_pairs']['DOM_correct_AX_incorrect']} / {mcnemar['discordant_pairs']['AX_correct_DOM_incorrect']} |",
        f"| Exact McNemar p-value (n = {mcnemar['paired_variant_count']} paired variants; power is very low) | {_format(mcnemar['exact_p_value'])} |",
        "",
        "### Reference comparison on confirmed W3C mappings (provisional reference)",
        "",
        "| Engine | Eligible variants | Classified | Coverage | Precision [95% CI] | Recall [95% CI] | F1 | Accuracy [95% CI] |",
        "|---|---:|---:|---:|---|---|---:|---|",
        f"| DOM | {dom['eligible_reference_variants']} | {dom['sample_size']} | {_format(dom['sample_size'] / dom['eligible_reference_variants'] if dom['eligible_reference_variants'] else None)} | {_with_ci(dom['precision'], dom['precision_ci95'])} | {_with_ci(dom['recall'], dom['recall_ci95'])} | {_format(dom['f1'])} | {_with_ci(dom['accuracy'], dom['accuracy_ci95'])} |",
        f"| AX | {ax['eligible_reference_variants']} | {ax['sample_size']} | {_format(ax['sample_size'] / ax['eligible_reference_variants'] if ax['eligible_reference_variants'] else None)} | {_with_ci(ax['precision'], ax['precision_ci95'])} | {_with_ci(ax['recall'], ax['recall_ci95'])} | {_format(ax['f1'])} | {_with_ci(ax['accuracy'], ax['accuracy_ci95'])} |",
        "",
        "A perfect score on a small set of purpose-built fixtures is expected because the rules were written for "
        "those fixtures; it does not estimate either engine's performance on real websites. Wilson intervals are "
        "wide because n is small.",
        "",
        "### Results by the proposal's categories (descriptive counts, Wilson 95% intervals)",
        "",
        "| Category | Engine | Variants | Classified | Correct | Not testable | Accuracy [95% CI] |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for letter, block in analysis["proposal_category_results"].items():
        for engine in ("DOM", "AX"):
            row = block["all_pass_fail_reference"][engine]
            lines.append(
                f"| {letter}: {block['name']} ({', '.join(block['cases'])}) | {engine} | {row['variants']} "
                f"| {row['classifiable']} | {row['correct']} | {row['not_testable_or_unstable']} "
                f"| {_with_ci(row['accuracy'], row['accuracy_ci95'])} |"
            )
    navigation = analysis.get("navigation_analysis", {})
    navigation_rows = navigation.get("by_navigation", {})
    lines.extend(
        [
            "",
            "### Results by navigation method",
            "",
            "Each condition is analyzed separately over the same variants; direct and in-app navigation "
            "are not counted as independent samples. Variant-level aggregate results above are classifiable "
            "only when available navigation methods agree.",
            "",
            "| Navigation method | Engine | Eligible variants | Classified | Coverage | Accuracy |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for method, engines in navigation_rows.items():
        for engine in ("DOM", "AX"):
            row = engines[engine]
            eligible_count = analysis["classification_by_engine"][engine]["eligible_reference_variants"]
            lines.append(
                f"| {method} | {engine} | {eligible_count} | {row['sample_size']} "
                f"| {_format(row['sample_size'] / eligible_count if eligible_count else None)} "
                f"| {_format(row['accuracy'])} |"
            )
    if navigation.get("cross_navigation_consistency"):
        lines.extend(
            [
                "",
                "| Engine | Compared variants | Consistent | Classifiable and consistent | Inconsistent | Missing method |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for engine, row in navigation["cross_navigation_consistency"].items():
            lines.append(
                f"| {engine} | {row['compared_variant_count']} | {row['consistent_variant_count']} "
                f"| {row['classifiable_consistent_variant_count']} | {row['inconsistent_variant_count']} "
                f"| {row['missing_navigation_variant_count']} |"
            )
    lines.extend(
        [
            "",
            "Variants with a NOT_TESTABLE reference (TC08) are excluded from these counts and listed below. "
            "This table includes the interpretive and extension cases, which are reported separately in the next table.",
            "",
            "### Interpretive and extension cases (reported separately)",
            "",
            f"Cases: {', '.join(separate['cases'])}.",
            "",
            "| Engine | Variants | Classified | Correct | Not testable | Accuracy [95% CI] |",
            "|---|---:|---:|---:|---:|---|",
            f"| DOM | {separate['DOM']['variants']} | {separate['DOM']['classifiable']} | {separate['DOM']['correct']} | {separate['DOM']['not_testable_or_unstable']} | {_with_ci(separate['DOM']['accuracy'], separate['DOM']['accuracy_ci95'])} |",
            f"| AX | {separate['AX']['variants']} | {separate['AX']['classifiable']} | {separate['AX']['correct']} | {separate['AX']['not_testable_or_unstable']} | {_with_ci(separate['AX']['accuracy'], separate['AX']['accuracy_ci95'])} |",
            "",
            f"Seeded defects reported as FAIL by neither engine: {', '.join(analysis['defects_missed_by_both_engines']) or 'none'}. "
            f"Variants whose reference is NOT_TESTABLE (not scored): {', '.join(analysis['reference_not_scored']) or 'none'}.",
            "",
            "### Separate keyboard and widget assertions",
            "",
            "| Engine | Secondary assertions | Classified | Reference accuracy |",
            "|---|---:|---:|---:|",
            f"| DOM | {dom_secondary['eligible_assertions']} | {dom_secondary['sample_size']} | {_format(dom_secondary['accuracy'])} |",
            f"| AX | {ax_secondary['eligible_assertions']} | {ax_secondary['sample_size']} | {_format(ax_secondary['accuracy'])} |",
            "",
            "These values compare predictions with predeclared expected fixture outcomes. They must not be "
            "presented as accuracy against independently validated ground truth until the manual review record is complete.",
            "",
            "### Repeatability",
            "",
            "| Engine | Variants | Classified (PASS/FAIL) | NOT_TESTABLE | Stable among classified | Repeatability rate |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for engine in ("DOM", "AX"):
        info = repeatability.get(engine, {})
        lines.append(
            f"| {engine} | {info.get('variant_count', 0)} | {info.get('classified_variant_count', 0)} "
            f"| {info.get('not_testable_variant_count', 0)} | {info.get('fully_stable_variant_count', 0)} "
            f"| {_format(info.get('repeatability_rate'))} |"
        )
    lines.extend(
        [
            "",
            "Each browser run starts from a fresh context, so repeat runs are deterministic apart from timing. "
            "Stability is therefore a sanity check, not evidence of generalisability.",
        ]
    )

    lines.extend(["", "## Disagreements and evidence", ""])
    lines.append(
        f"Of the differences listed below, {sum(1 for item in disagreements if item.get('type') == 'verdict_conflict')} "
        f"are verdict conflicts (one engine PASS, the other FAIL) and "
        f"{sum(1 for item in disagreements if item.get('type') == 'coverage_gap')} are coverage gaps "
        "(one engine returned NOT_TESTABLE). A coverage gap shows what an evidence source cannot decide; "
        "it is not evidence that the engines disagree about a defect."
    )
    lines.append("")
    if not disagreements:
        lines.append("No differences were observed between the engine verdicts in the captured run.")
    for disagreement in disagreements:
        lines.extend(
            [
                f"### {disagreement['test_case']} — {disagreement['variant']}",
                "",
                f"- Navigation condition: `{disagreement.get('access_method', 'unspecified')}`",
                f"- DOM: `{disagreement['dom_verdict']}` ({disagreement['dom_rule']}) — {disagreement['dom_evidence']}",
                f"- AX: `{disagreement['ax_verdict']}` ({disagreement['ax_rule']}) — {disagreement['ax_evidence']}",
                f"- Evidence-source hypothesis: {disagreement['information_source_hypothesis']}",
                f"- DOM evidence: `{disagreement['dom_snapshot']}`",
                f"- AX evidence: `{disagreement['ax_snapshot']}`",
                f"- Status: `{disagreement['review_status']}`; reviewer adjudication is still required.",
                "",
            ]
        )
    lines.extend(
        [
            "## Repeatability investigation",
            "",
        ]
    )
    if unstable_variants:
        for item in unstable_variants:
            lines.extend(
                [
                    f"- `{item['test_case']}/{item['variant']}` ({item['engine']}): "
                    f"{item['verdict_counts']} across {item['runs']} runs.",
                ]
            )
        lines.extend(
            [
                "These variants require investigation before interpreting majority verdicts; "
                "repeat count is not an increase to the statistical sample size.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "No classifiable variant had differing verdicts across its repeated captures. "
                "AX `NOT_TESTABLE` classifications are not treated as repeatability successes.",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation",
            "",
            "The controlled fixture illustrates that the evidence sources expose different kinds of evidence, "
            "without demonstrating general superiority. DOM inspection reveals authored relationships and interaction state; the Accessibility Tree "
            "exposes browser-computed roles, names, and states. Neither structural engine evaluates rendered "
            "contrast or focus-indicator pixels. Conversely, DOM attributes do not by themselves prove "
            "computed accessibility semantics. A `NOT_TESTABLE` verdict is a coverage limitation, never a pass.",
            "",
            "These results do not establish that one engine is generally superior. The test bed is small, "
            "criterion mappings for focus cases are interpretive, visual checks are constrained to simple "
            "renderings, and the reference labels still require human review.",
            "",
            "## Manual validation requirements",
            "",
            "Criterion mapping rationale and official sources are in `testcases/mapping_review.md`.",
            "",
            "## Limitations and required validation",
            "",
            "1. Complete independent manual validation of all reference outcomes and attach evidence; use a screen reader for live-region behavior.",
            "2. Reassess interpretive WCAG mappings for TC11 and TC12 and review the ACT 6cfa84 applicability record.",
            "3. Inspect TC13 screenshots and verify effective text contrast/rendering for TC14.",
            "4. Repeat the confirmatory ten-run experiment only after ground truth is approved; preserve this pilot unchanged.",
            "5. Confirm the final project scope and validation claims before broader publication.",
            "",
            "## Reproducibility artifacts",
            "",
            f"- Raw experiment JSON: `{_display_path(experiment_path)}`",
            f"- Analysis JSON: `{_display_path(analysis_path)}`",
            f"- Disagreement review JSON: `{_display_path(disagreement_path)}`",
        ]
    )
    for figure in analysis.get("figures", []):
        lines.append(f"- Figure: `{figure}`")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an evidence-backed research report.")
    parser.add_argument("experiment", type=Path)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("disagreements", type=Path)
    args = parser.parse_args()
    print(create_report(args.experiment, args.analysis, args.disagreements))


if __name__ == "__main__":
    main()
