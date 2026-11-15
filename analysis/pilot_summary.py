"""Descriptive counts for a one-repetition pilot result bundle."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def summarize(path: Path) -> dict:
    bundle = json.loads(path.read_text(encoding="utf-8"))
    results = bundle.get("results", [])
    verdict_counts = {}
    for engine in ("DOM", "AX"):
        counts = Counter(
            str(row.get("verdict", "UNKNOWN"))
            for row in results
            if str(row.get("engine", "")).upper() == engine
        )
        verdict_counts[engine] = {
            verdict: counts[verdict]
            for verdict in ("PASS", "FAIL", "NOT_TESTABLE", "INAPPLICABLE", "UNKNOWN")
        }
    variants = {(row.get("test_case"), row.get("variant")) for row in results}
    return {
        "run_id": bundle.get("execution_metadata", {}).get("run_id"),
        "variants": bundle.get("variant_count", len(variants)),
        "captures": bundle.get("completed_execution_count", bundle.get("execution_attempt_count", 0)),
        "result_count": len(results),
        "verdict_counts": verdict_counts,
        "execution_failures": len(bundle.get("execution_failures", [])),
        "study_mode": bundle.get("study_mode", "pilot"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="One-repetition pilot JSON bundle")
    args = parser.parse_args()
    print(json.dumps(summarize(args.input), indent=2))


if __name__ == "__main__":
    main()
