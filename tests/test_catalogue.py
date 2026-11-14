import json
from pathlib import Path

from testcases.generate_specs import build_specifications

ROOT = Path(__file__).resolve().parents[1]


def test_catalogue_and_reference_cover_all_14_paired_cases():
    catalogue = json.loads((ROOT / "testcases" / "catalogue.json").read_text(encoding="utf-8"))
    ground_truth = json.loads((ROOT / "testcases" / "ground_truth.json").read_text(encoding="utf-8"))
    assert len(catalogue["test_cases"]) == 14
    assert len(catalogue["variants"]) == 2
    assert len(ground_truth["expected_results"]) == 28
    assert len(build_specifications(catalogue, ground_truth)) == 28


def test_ground_truth_does_not_claim_human_validation():
    ground_truth = json.loads((ROOT / "testcases" / "ground_truth.json").read_text(encoding="utf-8"))
    assert ground_truth["manual_validation"]["completed"] is False
    assert all(item["manual_validation"] == "pending" for item in ground_truth["expected_results"])
    assert ground_truth["reference_freeze"]["verified"] is False
    assert ground_truth["reference_freeze"]["commit"] is None
    assert ground_truth["expected_results_are_predeclared_not_observed"] is True


def test_interpretive_error_and_focus_cases_are_not_silently_promoted():
    ground_truth = json.loads((ROOT / "testcases" / "ground_truth.json").read_text(encoding="utf-8"))
    statuses = {
        item["test_case"]: item["criterion_status"]
        for item in ground_truth["expected_results"]
    }
    assert statuses["TC08"] == "interpretive"
    assert statuses["TC11"] == "interpretive"
    assert statuses["TC12"] == "interpretive"


def test_fixture_scope_and_tc03_keyboard_assertions_are_explicit():
    catalogue = json.loads((ROOT / "testcases" / "catalogue.json").read_text(encoding="utf-8"))
    ground_truth = json.loads((ROOT / "testcases" / "ground_truth.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in catalogue["test_cases"]}
    assert "not a universal label checker" in cases["TC02"]["scope_note"]
    assert cases["TC03"]["separate_assertions"] == [
        "programmatic button role/name",
        "sequential keyboard focusability",
        "Enter/Space activation after focus",
    ]
    tc03 = {item["variant"]: item for item in ground_truth["expected_results"] if item["test_case"] == "TC03"}
    assert tc03["defective"]["sub_assertions"] == {
        "sequential keyboard focusability": "FAIL",
        "Enter/Space activation after focus": "NOT_TESTABLE",
    }
