from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from statsmodels.stats.contingency_tables import mcnemar

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_PATH = ROOT / "testcases" / "ground_truth.json"
OUTPUT_JSON = ROOT / "reports" / "json"
OUTPUT_CSV = ROOT / "reports" / "csv"
OUTPUT_FIGURES = ROOT / "reports" / "figures"
CLASSIFIABLE = {"PASS", "FAIL"}


def wilson_interval(successes: int, total: int, z: float = 1.959964) -> list[float] | None:
    """95% Wilson score interval for a proportion; None when total is 0."""
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def _majority_verdict(verdicts: list[str]) -> tuple[str, bool]:
    known = [verdict for verdict in verdicts if verdict in CLASSIFIABLE]
    if not known:
        return "NOT_TESTABLE", False
    counts = Counter(known)
    maximum = max(counts.values())
    leaders = [verdict for verdict, count in counts.items() if count == maximum]
    if len(leaders) != 1:
        return "UNSTABLE", False
    return leaders[0], len(known) == len(verdicts) and len(counts) == 1


def _confusion(predictions: list[tuple[str, str]]) -> dict[str, int]:
    counts = {"true_positive": 0, "false_positive": 0, "false_negative": 0, "true_negative": 0}
    for expected, predicted in predictions:
        if expected == "FAIL" and predicted == "FAIL":
            counts["true_positive"] += 1
        elif expected == "PASS" and predicted == "FAIL":
            counts["false_positive"] += 1
        elif expected == "FAIL" and predicted == "PASS":
            counts["false_negative"] += 1
        elif expected == "PASS" and predicted == "PASS":
            counts["true_negative"] += 1
    return counts


def _classification_metrics(predictions: list[tuple[str, str]]) -> dict[str, Any]:
    counts = _confusion(predictions)
    tp, fp, fn, tn = (
        counts["true_positive"],
        counts["false_positive"],
        counts["false_negative"],
        counts["true_negative"],
    )
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {
        "sample_size": len(predictions),
        "coverage": len(predictions),
        "confusion_matrix": {
            "labels": ["expected defect", "expected control"],
            "predicted_fail": [tp, fp],
            "predicted_pass": [fn, tn],
        },
        **counts,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": (tp + tn) / len(predictions) if predictions else None,
        "precision_ci95": wilson_interval(tp, tp + fp),
        "recall_ci95": wilson_interval(tp, tp + fn),
        "accuracy_ci95": wilson_interval(tp + tn, len(predictions)),
    }


def _cohen_kappa(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    if not pairs:
        return {"sample_size": 0, "agreement_rate": None, "cohens_kappa": None, "confusion": {}}
    labels = ["PASS", "FAIL"]
    table = {left: {right: 0 for right in labels} for left in labels}
    for left, right in pairs:
        table[left][right] += 1
    size = len(pairs)
    observed = sum(table[label][label] for label in labels) / size
    left_marginal = {label: sum(table[label].values()) / size for label in labels}
    right_marginal = {label: sum(table[row][label] for row in labels) / size for label in labels}
    expected = sum(left_marginal[label] * right_marginal[label] for label in labels)
    kappa = (observed - expected) / (1 - expected) if expected != 1 else None
    return {
        "sample_size": size,
        "agreement_count": sum(table[label][label] for label in labels),
        "agreement_rate": observed,
        "cohens_kappa": kappa,
        "confusion": table,
    }


def _combine_navigation_verdicts(
    verdicts: dict[str, str], required_methods: list[str]
) -> str:
    if not required_methods:
        return "NOT_TESTABLE"
    if any(method not in verdicts for method in required_methods):
        return "UNSTABLE"
    values = [verdicts[method] for method in required_methods]
    if len(set(values)) == 1:
        return values[0]
    return "UNSTABLE"


def _access_method(result: dict[str, Any]) -> str:
    return result.get("access_method") or (result.get("metadata") or {}).get(
        "access_method", "unspecified"
    )


def _majority_results(
    results: list[dict[str, Any]],
    required_methods: list[str] | None = None,
) -> tuple[
    dict[tuple[str, str, str], str],
    dict[str, Any],
    dict[tuple[str, str, str, str], str],
]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    required_methods = required_methods or sorted(
        {_access_method(row) for row in results}
    )
    for result in results:
        grouped[
            (
                result["test_case"],
                result["variant"],
                result["engine"],
                _access_method(result),
            )
        ].append(result)

    navigation_majority: dict[tuple[str, str, str, str], str] = {}
    navigation_rows = []
    variants_by_engine: dict[tuple[str, str, str], dict[str, str]] = defaultdict(dict)
    for (test_case, variant, engine, access_method), rows in sorted(grouped.items()):
        verdict, stable = _majority_verdict([row["verdict"] for row in rows])
        navigation_majority[(test_case, variant, engine, access_method)] = verdict
        variants_by_engine[(test_case, variant, engine)][access_method] = verdict
        all_verdicts = Counter(row["verdict"] for row in rows)
        navigation_rows.append(
            {
                "test_case": test_case,
                "variant": variant,
                "engine": engine,
                "access_method": access_method,
                "runs": len(rows),
                "verdict": verdict,
                "stable": stable,
                "known_runs": sum(count for key, count in all_verdicts.items() if key in CLASSIFIABLE),
                "verdict_counts": dict(all_verdicts),
            }
        )

    majority: dict[tuple[str, str, str], str] = {}
    stability_rows = []
    consistency_rows = []
    for key, verdicts in sorted(variants_by_engine.items()):
        test_case, variant, engine = key
        verdict = _combine_navigation_verdicts(verdicts, required_methods)
        majority[key] = verdict
        selected_rows = [
            row for row in navigation_rows
            if (row["test_case"], row["variant"], row["engine"]) == key
        ]
        stable = (
            all(row["stable"] for row in selected_rows)
            and len(verdicts) == len(required_methods)
            and verdict != "UNSTABLE"
        )
        all_verdicts = Counter()
        for row in selected_rows:
            all_verdicts.update(row["verdict_counts"])
        majority[(test_case, variant, engine)] = verdict
        stability_rows.append(
            {
                "test_case": test_case,
                "variant": variant,
                "engine": engine,
                "runs": sum(row["runs"] for row in selected_rows),
                "verdict": verdict,
                "stable": stable,
                "known_runs": sum(count for key, count in all_verdicts.items() if key in CLASSIFIABLE),
                "verdict_counts": dict(all_verdicts),
                "navigation_verdicts": dict(verdicts),
            }
        )
        if len(required_methods) > 1:
            consistency_rows.append(
                {
                    "test_case": test_case,
                    "variant": variant,
                    "engine": engine,
                    "verdicts": dict(verdicts),
                    "consistent": len(verdicts) == len(required_methods) and len(set(verdicts.values())) == 1,
                    "classifiable_consistent": (
                        len(verdicts) == len(required_methods)
                        and len(set(verdicts.values())) == 1
                        and all(value in CLASSIFIABLE for value in verdicts.values())
                    ),
                }
            )
    by_engine: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stability_rows:
        by_engine[row["engine"]].append(row)
    summary = {}
    for engine, rows in by_engine.items():
        classified = [row for row in rows if row["known_runs"] > 0]
        summary[engine] = {
            "variant_count": len(rows),
            "classified_variant_count": len(classified),
            "fully_stable_variant_count": sum(row["stable"] for row in rows),
            "not_testable_variant_count": len(rows) - len(classified),
            "repeatability_rate": sum(row["stable"] for row in classified) / len(classified) if classified else None,
            "unknown_run_count": sum(
                row["runs"] - row["known_runs"] for row in rows
            ),
        }
    by_navigation: dict[str, dict[str, dict[str, int]]] = {}
    for access_method in required_methods:
        by_navigation[access_method] = {}
        for engine in ("DOM", "AX"):
            rows = [
                row for row in navigation_rows
                if row["access_method"] == access_method and row["engine"] == engine
            ]
            by_navigation[access_method][engine] = {
                "variant_count": len(rows),
                "classifiable_variant_count": sum(row["verdict"] in CLASSIFIABLE for row in rows),
                "not_testable_variant_count": sum(row["verdict"] == "NOT_TESTABLE" for row in rows),
                "unstable_variant_count": sum(row["verdict"] == "UNSTABLE" for row in rows),
            }
    return majority, {
        "summary": summary,
        "variants": stability_rows,
        "by_navigation": by_navigation,
        "cross_navigation_consistency": consistency_rows,
    }, navigation_majority


def _navigation_classification(
    navigation_majority: dict[tuple[str, str, str, str], str],
    required_methods: list[str],
    reference: dict[tuple[str, str], dict[str, Any]],
    eligible: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    by_method = {}
    for method in required_methods:
        by_method[method] = {}
        for engine in ("DOM", "AX"):
            pairs = []
            for key, expected in eligible.items():
                predicted = navigation_majority.get(
                    (key[0], key[1], engine, method), "NOT_TESTABLE"
                )
                if predicted in CLASSIFIABLE:
                    pairs.append((expected["expected_verdict"], predicted))
            metrics = _classification_metrics(pairs)
            metrics["eligible_reference_variants"] = len(eligible)
            metrics["not_testable_or_unstable_count"] = len(eligible) - len(pairs)
            by_method[method][engine] = metrics

    cross_navigation = {}
    if len(required_methods) > 1:
        for engine in ("DOM", "AX"):
            compared = []
            inconsistent = []
            missing = []
            for test_case, variant in sorted(reference):
                verdicts = {
                    method: navigation_majority.get(
                        (test_case, variant, engine, method), "MISSING"
                    )
                    for method in required_methods
                }
                if "MISSING" in verdicts.values():
                    missing.append({"test_case": test_case, "variant": variant, "verdicts": verdicts})
                else:
                    consistent = len(set(verdicts.values())) == 1
                    compared.append(
                        {
                            "test_case": test_case,
                            "variant": variant,
                            "verdicts": verdicts,
                            "consistent": consistent,
                            "classifiable_consistent": (
                                consistent and all(value in CLASSIFIABLE for value in verdicts.values())
                            ),
                        }
                    )
                    if not consistent:
                        inconsistent.append(
                            {"test_case": test_case, "variant": variant, "verdicts": verdicts}
                        )
            cross_navigation[engine] = {
                "compared_variant_count": len(compared),
                "consistent_variant_count": sum(row["consistent"] for row in compared),
                "classifiable_consistent_variant_count": sum(
                    row["classifiable_consistent"] for row in compared
                ),
                "inconsistent_variant_count": len(inconsistent),
                "missing_navigation_variant_count": len(missing),
                "inconsistencies": inconsistent,
                "missing_navigation": missing,
            }
    return {"by_navigation": by_method, "cross_navigation_consistency": cross_navigation}


def _rule_coverage(results: list[dict[str, Any]]) -> dict[str, Any]:
    primary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"runs": 0, "verdict_counts": Counter()}
    )
    secondary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"checks": 0, "verdict_counts": Counter()}
    )
    for result in results:
        key = f"{result['engine']}:{result['rule']}"
        primary[key]["runs"] += 1
        primary[key]["verdict_counts"][result["verdict"]] += 1
        for check in result.get("sub_checks", []):
            sub_key = f"{result['engine']}:{check['criterion']}:{check['rule']}"
            secondary[sub_key]["checks"] += 1
            secondary[sub_key]["verdict_counts"][check["verdict"]] += 1
    return {
        "primary_rules": {
            key: {
                "runs": value["runs"],
                "verdict_counts": dict(value["verdict_counts"]),
                "classifiable_count": sum(
                    count for verdict, count in value["verdict_counts"].items()
                    if verdict in CLASSIFIABLE
                ),
            }
            for key, value in sorted(primary.items())
        },
        "secondary_assertions": {
            key: {
                "checks": value["checks"],
                "verdict_counts": dict(value["verdict_counts"]),
                "classifiable_count": sum(
                    count for verdict, count in value["verdict_counts"].items()
                    if verdict in CLASSIFIABLE
                ),
            }
            for key, value in sorted(secondary.items())
        },
        "note": "Coverage is rule execution/classifiable output, not detection effectiveness.",
    }


def _sub_assertion_metrics(
    results: list[dict[str, Any]],
    reference: dict[tuple[str, str], dict[str, Any]],
    required_methods: list[str] | None = None,
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str, str, str], list[str]] = defaultdict(list)
    required_methods = required_methods or sorted(
        {_access_method(row) for row in results}
    )
    for result in results:
        for check in result.get("sub_checks", []):
            grouped[
                (
                    result["test_case"],
                    result["variant"],
                    result["engine"],
                    check["assertion"],
                    _access_method(result),
                )
            ].append(check["verdict"])

    report: dict[str, Any] = {}
    for engine in ("DOM", "AX"):
        expected_predictions = []
        not_testable = 0
        eligible_count = 0
        repeatability: dict[str, Any] = {}
        assertion_keys = sorted(
            {
                assertion
                for case_id, variant, check_engine, assertion, _ in grouped
                if check_engine == engine and (case_id, variant) in reference
                and assertion in reference[(case_id, variant)].get("sub_assertions", {})
            }
        )
        by_navigation = {}
        for assertion in assertion_keys:
            pairs = []
            stable_count = 0
            navigation_pairs = {method: [] for method in required_methods}
            for (case_id, variant), expected in reference.items():
                if assertion not in expected.get("sub_assertions", {}):
                    continue
                eligible_count += 1
                expected_verdict = expected["sub_assertions"][assertion]
                method_verdicts = {}
                method_stable = {}
                for method in required_methods:
                    verdicts = grouped.get((case_id, variant, engine, assertion, method), [])
                    if verdicts:
                        method_verdicts[method], method_stable[method] = _majority_verdict(verdicts)
                    else:
                        method_verdicts[method], method_stable[method] = "NOT_TESTABLE", False
                    if method_verdicts[method] in CLASSIFIABLE and expected_verdict in CLASSIFIABLE:
                        navigation_pairs[method].append(
                            (expected_verdict, method_verdicts[method])
                        )
                majority = _combine_navigation_verdicts(method_verdicts, required_methods)
                stable = (
                    all(method_stable.values())
                    and majority != "UNSTABLE"
                )
                stable_count += int(stable)
                if majority not in CLASSIFIABLE or expected_verdict not in CLASSIFIABLE:
                    not_testable += 1
                    continue
                pairs.append((expected_verdict, majority))
            expected_predictions.extend(pairs)
            repeatability[f"{assertion}"] = {
                "sample_size": len(pairs),
                "fully_stable_count": stable_count,
            }
            by_navigation[assertion] = {
                method: {
                    **_classification_metrics(pairs_for_method),
                    "eligible_assertions": sum(
                        assertion in item.get("sub_assertions", {})
                        for item in reference.values()
                    ),
                    "not_testable_or_missing_count": sum(
                        assertion in item.get("sub_assertions", {})
                        for item in reference.values()
                    ) - len(pairs_for_method),
                }
                for method, pairs_for_method in navigation_pairs.items()
            }
        metrics = _classification_metrics(expected_predictions)
        report[engine] = {
            **metrics,
            "eligible_assertions": eligible_count,
            "not_testable_or_missing_count": not_testable,
            "assertion_repeatability": repeatability,
            "by_navigation": by_navigation,
            "note": "Secondary assertion outcomes are analyzed separately from the primary rule verdicts.",
        }
    return report


def _is_confirmed(item: dict[str, Any]) -> bool:
    """Confirmed W3C mapping (including the ACT-rule case); interpretive and extension cases are separate."""
    return "confirmed" in item["criterion_status"]


def _engine_counts(
    keys: list[tuple[str, str]],
    reference: dict[tuple[str, str], dict[str, Any]],
    majority: dict[tuple[str, str, str], str],
    engine: str,
) -> dict[str, Any]:
    """Counts, precision/recall and Wilson intervals for one engine over a set of variants."""
    accepted = []
    not_testable = 0
    for case_id, variant in keys:
        predicted = majority.get((case_id, variant, engine), "NOT_TESTABLE")
        if predicted in CLASSIFIABLE:
            accepted.append((reference[(case_id, variant)]["expected_verdict"], predicted))
        else:
            not_testable += 1
    metrics = _classification_metrics(accepted)
    correct = sum(expected == predicted for expected, predicted in accepted)
    return {
        "variants": len(keys),
        "classifiable": len(accepted),
        "correct": correct,
        "not_testable_or_unstable": not_testable,
        "coverage": len(accepted) / len(keys) if keys else None,
        "coverage_ci95": wilson_interval(len(accepted), len(keys)),
        **{key: metrics[key] for key in (
            "true_positive", "false_positive", "false_negative", "true_negative",
            "precision", "recall", "f1", "accuracy",
            "precision_ci95", "recall_ci95", "accuracy_ci95",
        )},
    }


def analyze(bundle: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, Any]:
    reference = {
        (item["test_case"], item["variant"]): item
        for item in ground_truth["expected_results"]
    }
    execution_metadata = bundle.get("execution_metadata", {})
    required_methods = execution_metadata.get("navigation_methods")
    if not isinstance(required_methods, list) or not required_methods:
        required_methods = sorted(
            {_access_method(row) for row in bundle["results"]}
        )
    majority, stability, navigation_majority = _majority_results(
        bundle["results"],
        required_methods=required_methods,
    )
    eligible = {
        key: item
        for key, item in reference.items()
        if item["expected_verdict"] in CLASSIFIABLE and _is_confirmed(item)
    }
    separate_reference = {
        key: item
        for key, item in reference.items()
        if item["expected_verdict"] in CLASSIFIABLE and not _is_confirmed(item)
    }
    navigation_analysis = _navigation_classification(
        navigation_majority, required_methods, reference, eligible
    )
    per_engine = {}
    for engine in ("DOM", "AX"):
        accepted = []
        total_eligible = len(eligible)
        for key, expected in eligible.items():
            predicted = majority.get((key[0], key[1], engine), "NOT_TESTABLE")
            if predicted in CLASSIFIABLE:
                accepted.append((expected["expected_verdict"], predicted))
        per_engine[engine] = {
            **_classification_metrics(accepted),
            "eligible_reference_variants": total_eligible,
            "not_testable_or_unstable_count": total_eligible - len(accepted),
            "reference_status": ground_truth["status"],
        }

    agreement_pairs = []
    eligible_agreement_pairs = []
    for (test_case, variant), expected in reference.items():
        dom = majority.get((test_case, variant, "DOM"), "NOT_TESTABLE")
        ax = majority.get((test_case, variant, "AX"), "NOT_TESTABLE")
        if dom in CLASSIFIABLE and ax in CLASSIFIABLE:
            agreement_pairs.append((dom, ax))
            if (test_case, variant) in eligible:
                eligible_agreement_pairs.append((dom, ax))

    paired_correct = []
    for key, expected in eligible.items():
        dom = majority.get((key[0], key[1], "DOM"), "NOT_TESTABLE")
        ax = majority.get((key[0], key[1], "AX"), "NOT_TESTABLE")
        if dom in CLASSIFIABLE and ax in CLASSIFIABLE:
            paired_correct.append(
                (dom == expected["expected_verdict"], ax == expected["expected_verdict"])
            )
    both_correct = sum(dom and ax for dom, ax in paired_correct)
    dom_only_correct = sum(dom and not ax for dom, ax in paired_correct)
    ax_only_correct = sum(ax and not dom for dom, ax in paired_correct)
    neither_correct = sum(not dom and not ax for dom, ax in paired_correct)
    discordants = dom_only_correct + ax_only_correct
    statsmodels_result = mcnemar(
        [[both_correct, dom_only_correct], [ax_only_correct, neither_correct]],
        exact=True,
    )
    scipy_result = binomtest(min(dom_only_correct, ax_only_correct), discordants, 0.5).pvalue if discordants else 1.0
    mcnemar_report = {
        "paired_variant_count": len(paired_correct),
        "discordant_pairs": {
            "DOM_correct_AX_incorrect": dom_only_correct,
            "AX_correct_DOM_incorrect": ax_only_correct,
        },
        "both_correct": both_correct,
        "neither_correct": neither_correct,
        "exact_p_value": float(statsmodels_result.pvalue),
        "scipy_exact_binomial_p_value": float(scipy_result),
        "note": "Paired correctness uses the provisional reference only; interpretation/extension cases and unclassifiable engine results are excluded.",
    }

    categories = {}
    catalogue = json.loads((ROOT / "testcases" / "catalogue.json").read_text(encoding="utf-8"))
    case_categories = {case["id"]: case["category"] for case in catalogue["test_cases"]}
    grouped_category: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for (test_case, variant), expected in eligible.items():
        grouped_category[case_categories[test_case]].append((test_case, variant))
    for category, keys in grouped_category.items():
        categories[category] = {
            engine: {
                "eligible_variants": len(keys),
                "classifiable_variants": sum(
                    majority.get((case_id, variant, engine), "NOT_TESTABLE") in CLASSIFIABLE
                    for case_id, variant in keys
                ),
                "expected_failures_detected": sum(
                    reference[(case_id, variant)]["expected_verdict"] == "FAIL"
                    and majority.get((case_id, variant, engine)) == "FAIL"
                    for case_id, variant in keys
                ),
            }
            for engine in ("DOM", "AX")
        }

    # Proposal categories A-D (static markup, computed/hidden, dynamic, behaviour/visual)
    proposal_names = {
        case["proposal_category"]: case["proposal_category_name"] for case in catalogue["test_cases"]
    }
    case_proposal = {case["id"]: case["proposal_category"] for case in catalogue["test_cases"]}
    proposal_categories: dict[str, Any] = {}
    for letter in sorted(proposal_names):
        all_keys = [key for key in reference if case_proposal[key[0]] == letter]
        scored = [key for key in all_keys if reference[key]["expected_verdict"] in CLASSIFIABLE]
        confirmed_keys = [key for key in scored if key in eligible]
        proposal_categories[letter] = {
            "name": proposal_names[letter],
            "cases": sorted({key[0] for key in all_keys}),
            "variants_total": len(all_keys),
            "variants_with_pass_fail_reference": len(scored),
            "variants_reference_not_testable": len(all_keys) - len(scored),
            "confirmed_mappings_only": {
                engine: _engine_counts(confirmed_keys, reference, majority, engine)
                for engine in ("DOM", "AX")
            },
            "all_pass_fail_reference": {
                engine: _engine_counts(scored, reference, majority, engine)
                for engine in ("DOM", "AX")
            },
        }

    separate_keys = sorted(separate_reference)
    separate_report = {
        engine: _engine_counts(separate_keys, reference, majority, engine) for engine in ("DOM", "AX")
    }
    separate_report["cases"] = sorted({key[0] for key in separate_keys})
    separate_report["note"] = (
        "Interpretive and extension cases (TC11-TC14) are reported separately from confirmed W3C mappings, "
        "as the proposal requires. TC08 has a NOT_TESTABLE reference and is a coverage gap for both engines."
    )

    # Which seeded defects does neither engine report as FAIL?
    missed_by_both = sorted(
        f"{case_id}/{variant}"
        for (case_id, variant), item in reference.items()
        if item["expected_verdict"] == "FAIL"
        and majority.get((case_id, variant, "DOM")) != "FAIL"
        and majority.get((case_id, variant, "AX")) != "FAIL"
    )
    reference_not_scored = sorted(
        f"{case_id}/{variant}"
        for (case_id, variant), item in reference.items()
        if item["expected_verdict"] not in CLASSIFIABLE
    )

    # Verdict conflicts (PASS vs FAIL) are different from coverage gaps (one engine NOT_TESTABLE)
    verdict_conflicts = []
    coverage_gaps = []
    for (test_case, variant) in sorted(reference):
        dom = majority.get((test_case, variant, "DOM"), "NOT_TESTABLE")
        ax = majority.get((test_case, variant, "AX"), "NOT_TESTABLE")
        if dom in CLASSIFIABLE and ax in CLASSIFIABLE and dom != ax:
            verdict_conflicts.append(f"{test_case}/{variant}")
        elif (dom in CLASSIFIABLE) != (ax in CLASSIFIABLE):
            coverage_gaps.append(f"{test_case}/{variant}")
    disagreement_types = {
        "verdict_conflicts": verdict_conflicts,
        "coverage_gaps_one_engine_not_testable": coverage_gaps,
        "both_not_testable": sorted(
            f"{test_case}/{variant}"
            for (test_case, variant) in reference
            if majority.get((test_case, variant, "DOM"), "NOT_TESTABLE") not in CLASSIFIABLE
            and majority.get((test_case, variant, "AX"), "NOT_TESTABLE") not in CLASSIFIABLE
        ),
    }

    raw_frame = pd.DataFrame(bundle["results"])
    runtime = {}
    for engine, group in raw_frame.groupby("engine"):
        runtime[engine] = {
            "run_count": int(len(group)),
            "mean_seconds": float(group["execution_time"].mean()),
            "median_seconds": float(group["execution_time"].median()),
            "min_seconds": float(group["execution_time"].min()),
            "max_seconds": float(group["execution_time"].max()),
        }

    return {
        "schema_version": 1,
        "study_mode": bundle["study_mode"],
        "manual_ground_truth_validated": ground_truth["manual_validation"]["completed"],
        "reference_status": ground_truth["status"],
        "unit_of_analysis": "test variant; repeated executions are used only for stability assessment",
        "raw_result_count": int(len(bundle["results"])),
        "runs_per_variant": bundle["runs_per_variant"],
        "reference_variant_count": len(reference),
        "agreement": {
            "all_classifiable_variants": _cohen_kappa(agreement_pairs),
            "confirmed_mapping_reference_variants": _cohen_kappa(eligible_agreement_pairs),
        },
        "navigation_analysis": navigation_analysis,
        "classification_by_engine": per_engine,
        "rule_coverage": _rule_coverage(bundle["results"]),
        "secondary_assertion_classification": _sub_assertion_metrics(
            bundle["results"], reference, required_methods
        ),
        "mcnemar_exact": mcnemar_report,
        "repeatability": stability,
        "runtime": runtime,
        "category_descriptive_results": categories,
        "proposal_category_results": proposal_categories,
        "interpretive_and_extension_cases": separate_report,
        "defects_missed_by_both_engines": missed_by_both,
        "reference_not_scored": reference_not_scored,
        "disagreement_types": disagreement_types,
        "limitations": [
            "Expected outcomes are provisional and have not received independent manual/screen-reader review.",
            "Precision, recall, F1, accuracy, McNemar, and kappa are reference comparisons, not validated conformance accuracy.",
            "NOT_TESTABLE and INAPPLICABLE are never recoded as PASS.",
            "Rules are tailored to these purpose-built fixtures; results do not estimate general-purpose tool performance.",
            "Fresh-context repeats are largely deterministic and assess implementation stability, not robustness or generalisability.",
            "Direct URL and in-app navigation are repeated conditions on the same variants, not independent samples.",
            "Small sample size and controlled fixtures do not establish general superiority.",
        ],
    }


def create_figures(report: dict[str, Any], raw_results: list[dict[str, Any]], run_id: str) -> list[str]:
    OUTPUT_FIGURES.mkdir(parents=True, exist_ok=True)
    paths = []
    agreement = report["agreement"]["confirmed_mapping_reference_variants"]["confusion"]
    labels = ["PASS", "FAIL"]
    matrix = np.array(
        [[agreement.get(label, {}).get(other, 0) for other in labels] for label in labels]
    )
    figure, axis = plt.subplots(figsize=(5, 4))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set_xticks(range(2), labels=labels)
    axis.set_yticks(range(2), labels=labels)
    axis.set_xlabel("Accessibility Tree verdict")
    axis.set_ylabel("DOM verdict")
    axis.set_title("Paired engine verdicts (provisional confirmed mappings)")
    for row in range(2):
        for column in range(2):
            axis.text(column, row, str(matrix[row, column]), ha="center", va="center")
    figure.colorbar(image, ax=axis, label="Variant count")
    figure.tight_layout()
    path = OUTPUT_FIGURES / f"agreement_{run_id}.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    paths.append(str(path.relative_to(ROOT)))

    # Coverage by the proposal's categories: how many variants each engine could classify (PASS/FAIL)
    categories = report["proposal_category_results"]
    letters = sorted(categories)
    width = 0.38
    figure, axis = plt.subplots(figsize=(7.5, 4.2))
    for offset, (engine, colour) in enumerate((("DOM", "#355f9c"), ("AX", "#56805d"))):
        values = [categories[letter]["all_pass_fail_reference"][engine]["coverage"] or 0 for letter in letters]
        positions = [index + (offset - 0.5) * width for index in range(len(letters))]
        axis.bar(positions, values, width, label=engine, color=colour)
    axis.set_xticks(range(len(letters)), [f"{letter}: {categories[letter]['name']}" for letter in letters], fontsize=7)
    axis.set_ylim(0, 1.05)
    axis.set_ylabel("Share of PASS/FAIL reference variants classified")
    axis.set_title("Coverage by category (NOT_TESTABLE is a coverage gap, not a pass)")
    axis.legend()
    figure.tight_layout()
    path = OUTPUT_FIGURES / f"coverage_{run_id}.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    paths.append(str(path.relative_to(ROOT)))

    repeatability = report["repeatability"]["summary"]
    engines = list(repeatability)
    rates = [repeatability[engine]["repeatability_rate"] or 0 for engine in engines]
    figure, axis = plt.subplots(figsize=(6, 4))
    axis.bar(engines, rates, color=["#355f9c", "#56805d"][:len(engines)])
    axis.set_ylim(0, 1)
    axis.set_ylabel("Unanimous classified variants / classified variants")
    axis.set_title("Repeatability (not accuracy)")
    figure.tight_layout()
    path = OUTPUT_FIGURES / f"repeatability_{run_id}.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    paths.append(str(path.relative_to(ROOT)))
    return paths


def analyze_file(input_path: Path) -> tuple[Path, Path, list[str]]:
    bundle = json.loads(input_path.read_text(encoding="utf-8"))
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    report = analyze(bundle, ground_truth)
    run_id = bundle["execution_metadata"]["run_id"]
    report["run_id"] = run_id
    report["figures"] = create_figures(report, bundle["results"], run_id)
    OUTPUT_JSON.mkdir(parents=True, exist_ok=True)
    OUTPUT_CSV.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_JSON / f"analysis_{run_id}.json"
    csv_path = OUTPUT_CSV / f"analysis_{run_id}.csv"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary_rows = []
    for engine, values in report["classification_by_engine"].items():
        summary_rows.append({"engine": engine, "metric_group": "reference_classification", **values})
    for engine, values in report["repeatability"]["summary"].items():
        summary_rows.append({"engine": engine, "metric_group": "repeatability", **values})
    pd.DataFrame(summary_rows).to_csv(csv_path, index=False)
    return json_path, csv_path, report["figures"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze paired DOM and AX experiment results.")
    parser.add_argument("input", type=Path, help="Raw experiment JSON bundle.")
    args = parser.parse_args()
    json_path, csv_path, figures = analyze_file(args.input)
    print(f"Analysis JSON: {json_path}")
    print(f"Analysis CSV: {csv_path}")
    for figure in figures:
        print(f"Figure: {figure}")


if __name__ == "__main__":
    main()
