from __future__ import annotations

from typing import Any

ALLOWED_VERDICTS = {"PASS", "FAIL", "INAPPLICABLE", "NOT_TESTABLE"}


def build_result(
    *,
    test_case: str,
    variant: str,
    engine: str,
    criterion: str,
    verdict: str,
    rule: str,
    evidence: str,
    execution_time: float,
    run_index: int = 0,
    criterion_status: str = "confirmed_mapping",
    sub_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if verdict not in ALLOWED_VERDICTS:
        raise ValueError(f"Unsupported verdict: {verdict}")
    return {
        "test_case": test_case,
        "variant": variant,
        "engine": engine,
        "criterion": criterion,
        "criterion_status": criterion_status,
        "verdict": verdict,
        "rule": rule,
        "evidence": evidence,
        "execution_time": round(execution_time, 6),
        "run_index": run_index,
        "sub_checks": sub_checks or [],
    }
