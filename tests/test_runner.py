import pytest

from runner.experiment_runner import _argument_parser, run_experiment


def test_pilot_runner_defaults_to_exactly_one_run():
    assert _argument_parser().parse_args([]).runs == 1
    with pytest.raises(SystemExit):
        _argument_parser().parse_args(["--runs", "10"])


def test_experiment_runner_rejects_multiple_runs_before_starting_browser():
    with pytest.raises(ValueError, match="exactly one repetition"):
        run_experiment("http://127.0.0.1:5000", 2)
