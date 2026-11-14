from analysis.metrics import _classification_metrics, _cohen_kappa, _majority_verdict


def test_majority_collapses_repeats_and_marks_instability():
    assert _majority_verdict(["FAIL", "FAIL", "PASS"]) == ("FAIL", False)
    assert _majority_verdict(["PASS", "PASS"]) == ("PASS", True)
    assert _majority_verdict(["NOT_TESTABLE", "FAIL"]) == ("FAIL", False)
    assert _majority_verdict(["PASS", "FAIL"]) == ("UNSTABLE", False)


def test_binary_metrics_do_not_count_unknown_results_as_pass():
    result = _classification_metrics(
        [("FAIL", "FAIL"), ("FAIL", "PASS"), ("PASS", "FAIL"), ("PASS", "PASS")]
    )
    assert result["sample_size"] == 4
    assert result["true_positive"] == 1
    assert result["false_negative"] == 1
    assert result["false_positive"] == 1
    assert result["true_negative"] == 1
    assert result["precision"] == result["recall"] == result["f1"] == 0.5


def test_cohen_kappa_reports_sample_size_and_observed_agreement():
    result = _cohen_kappa([("PASS", "PASS"), ("FAIL", "PASS")])
    assert result["sample_size"] == 2
    assert result["agreement_count"] == 1
    assert result["agreement_rate"] == 0.5
    assert result["cohens_kappa"] == 0.0

