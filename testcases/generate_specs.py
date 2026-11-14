from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def build_specifications(catalogue: dict[str, Any], ground_truth: dict[str, Any]) -> list[dict[str, Any]]:
    expected = {
        (item["test_case"], item["variant"]): item
        for item in ground_truth["expected_results"]
    }
    specifications = []
    for case in catalogue["test_cases"]:
        for variant in catalogue["variants"]:
            reference = expected.get((case["id"], variant))
            if reference is None:
                raise ValueError(f"Missing expected result for {case['id']} / {variant}.")
            specifications.append(
                {
                    "test_case": case["id"],
                    "variant": variant,
                    "criterion": case["criterion"],
                    "secondary_criterion": case.get("secondary_criterion"),
                    "separate_assertions": case.get("separate_assertions", []),
                    "mapping_status": case["mapping_status"],
                    "failure_condition": case["failure_condition"],
                    "preconditions": case["preconditions"],
                    "interaction_steps": case["interaction_steps"],
                    "expected_outcome": case["expected_outcome"],
                    "expected_reference_verdict": reference["expected_verdict"],
                    "expected_sub_assertions": reference.get("sub_assertions", {}),
                    "criterion_status": reference["criterion_status"],
                    "manual_verification_method": case["manual_verification"],
                    "manual_validation_status": reference["manual_validation"],
                    "evidence": case["evidence"],
                    "dom_testability": case["dom_testability"],
                    "accessibility_tree_testability": case["accessibility_tree_testability"],
                    "limitations": case["limitations"],
                    "ground_truth_status": ground_truth["status"],
                }
            )
    if len(expected) != len(specifications):
        raise ValueError(
            f"Expected results count ({len(expected)}) does not match specification count ({len(specifications)})."
        )
    return specifications


def main() -> None:
    catalogue = json.loads((ROOT / "catalogue.json").read_text(encoding="utf-8"))
    ground_truth = json.loads((ROOT / "ground_truth.json").read_text(encoding="utf-8"))
    output = ROOT / "specifications"
    output.mkdir(parents=True, exist_ok=True)
    for spec in build_specifications(catalogue, ground_truth):
        path = output / f"{spec['test_case']}-{spec['variant']}.json"
        path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"Wrote {len(catalogue['test_cases']) * len(catalogue['variants'])} specifications to {output}")


if __name__ == "__main__":
    main()
