from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Error as PlaywrightError, Page, sync_playwright

from engines.ax_engine import evaluate as evaluate_ax
from engines.dom_engine import evaluate as evaluate_dom

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_PATH = ROOT / "testcases" / "catalogue.json"
GROUND_TRUTH_PATH = ROOT / "testcases" / "ground_truth.json"
OUTPUT_JSON = ROOT / "reports" / "json"
OUTPUT_CSV = ROOT / "reports" / "csv"
OUTPUT_EVIDENCE = ROOT / "reports" / "evidence"


AX_TARGET_EXPRESSIONS = {
    "TC01": {"primary": "uniqueElement('[data-test-image=\"informative\"]')"},
    "TC02": {"primary": "uniqueElement('#email')"},
    "TC03": {
        "primary": "uniqueElement('#custom-action')",
        "status": "uniqueElement('#activation-status')",
    },
    "TC04": {"primary": "uniqueElement('#search-action')"},
    "TC05": {"primary": "uniqueElement('#hidden-action')"},
    "TC06": {
        "primary": "uniqueElement('#shadow-action', document.querySelector('research-action')?.shadowRoot)",
    },
    "TC07": {"primary": "uniqueElement('#status-message')"},
    "TC08": {"primary": "uniqueElement('#account-email')"},
    "TC09": {
        "primary": "uniqueElement('#tab-settings')",
        "disclosure": "uniqueElement('#disclosure')",
    },
    "TC11": {"primary": "uniqueElement('#main-content')"},
}
TC12_OPEN_TARGETS = {
    "dialog": "uniqueElement('#research-dialog')",
    "close": "uniqueElement('#dialog-close')",
}
TC12_CLOSED_TARGETS = {
    "opener": "uniqueElement('#dialog-opener')",
}


def _read_accessibility_tree(
    page: Page,
    test_case: str,
    target_expressions: dict[str, str] | None = None,
) -> dict[str, Any]:
    session = page.context.new_cdp_session(page)
    try:
        tree = session.send("Accessibility.getFullAXTree")
        expressions = target_expressions if target_expressions is not None else AX_TARGET_EXPRESSIONS.get(test_case, {})
        target_ids: dict[str, int] = {}
        for name, target_expression in expressions.items():
            result = session.send(
                "Runtime.evaluate",
                {
                    "expression": (
                        f"(() => {{ const uniqueElement = (selector, root = document) => {{ "
                        "const matches = root ? root.querySelectorAll(selector) : []; "
                        "return matches.length === 1 ? matches[0] : null; }; "
                        f"return {target_expression}; }})()"
                    ),
                    "returnByValue": False,
                },
            )
            if result.get("exceptionDetails"):
                raise RuntimeError(f"Unable to map AX target {name!r}: {result['exceptionDetails']!r}")
            remote_object = result.get("result", {})
            object_id = remote_object.get("objectId")
            if not object_id:
                continue
            described = session.send("DOM.describeNode", {"objectId": object_id}).get("node", {})
            backend_node_id = described.get("backendNodeId")
            if isinstance(backend_node_id, int):
                target_ids[name] = backend_node_id
            session.send("Runtime.releaseObject", {"objectId": object_id})
        return {**tree, "target_backend_node_ids": target_ids}
    finally:
        session.detach()


def _focus_state(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const element = document.activeElement;
          return {
            tag: element?.tagName?.toLowerCase() || null,
            id: element?.id || null,
            role: element?.getAttribute("role") || null
          };
        }"""
    )


def _dom_snapshot(page: Page, interaction_states: dict[str, Any]) -> dict[str, Any]:
    return page.evaluate(
        """({ interactionStates }) => {
          const shadowRoots = [];
          const visit = (root) => {
            for (const element of root.querySelectorAll("*")) {
              if (element.shadowRoot) {
                shadowRoots.push({
                  host: element.localName,
                  hostId: element.id || null,
                  html: element.shadowRoot.innerHTML
                });
                visit(element.shadowRoot);
              }
            }
          };
          visit(document);
          return {
            url: location.href,
            title: document.title,
            html: document.documentElement.outerHTML,
            shadow_roots: shadowRoots.map((root) => ({
              host: root.host,
              host_id: root.hostId,
              html: root.html
            })),
            interaction_states: interactionStates
          };
        }""",
        {"interactionStates": interaction_states},
    )


def _navigate(
    page: Page,
    base_url: str,
    test_case: str,
    variant: str,
    access_method: str,
) -> None:
    target = f"{base_url}/#/case/{test_case}/{variant}"
    if access_method == "in_app_navigation":
        page.goto(base_url, wait_until="networkidle")
        page.wait_for_selector('html[data-app-ready="true"]')
        page.get_by_role("link", name="Test bed", exact=True).click()
        page.wait_for_function("window.location.hash === '#/test-bed'")
        case_route = f'#/case/{test_case}/{variant}'
        case_link = page.locator(f'.case-list a[href="{case_route}"]')
        if case_link.count() != 1:
            raise RuntimeError(f"Expected one in-app link for {case_route}; found {case_link.count()}.")
        case_link.click()
    elif access_method == "direct_url":
        page.goto(target, wait_until="networkidle")
    else:
        raise ValueError(f"Unknown access method: {access_method}")
    page.wait_for_function("document.documentElement.dataset.appReady === 'true'")
    page.wait_for_selector(f'[data-test-case="{test_case}"][data-variant="{variant}"]')


def _capture_variant(
    browser: Browser,
    test_case: str,
    variant: str,
    run_index: int,
    base_url: str,
    run_id: str,
    access_method: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    context = browser.new_context(viewport={"width": 1280, "height": 800}, locale="en-GB")
    try:
        page = context.new_page()
        console_errors: list[str] = []
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        _navigate(page, base_url, test_case, variant, access_method)

        states: dict[str, Any] = {}
        ax_states: dict[str, Any] = {}
        initial_dom = _dom_snapshot(page, {})
        initial_ax = _read_accessibility_tree(page, test_case)
        if not isinstance(initial_dom.get("html"), str) or not initial_ax.get("nodes"):
            raise RuntimeError("The initial DOM or Accessibility Tree snapshot is incomplete.")
        ax_states["initial"] = initial_ax

        if test_case == "TC03":
            tab_sequence = []
            ax_tab_sequence = []
            target_focused = False
            for _ in range(24):
                page.keyboard.press("Tab")
                focus = _focus_state(page)
                tab_sequence.append(focus)
                ax_tab_sequence.append(_read_accessibility_tree(page, test_case))
                if focus.get("id") == "custom-action":
                    target_focused = True
                    break
            if target_focused:
                page.keyboard.press("Enter")
                page.keyboard.press("Space")
            activation_count = page.locator("#custom-action").get_attribute("data-activated")
            states["tab_sequence"] = tab_sequence
            ax_states["tab_sequence"] = ax_tab_sequence
            states["keyboard_activation"] = {
                "tab_sequence_attempted": True,
                "target_focused_by_tab": target_focused,
                "activation_attempted": target_focused,
                "activation_count": activation_count,
            }
        elif test_case == "TC05":
            tab_sequence = []
            ax_tab_sequence = []
            for _ in range(12):
                page.keyboard.press("Tab")
                focus = _focus_state(page)
                tab_sequence.append(focus)
                ax_tab_sequence.append(_read_accessibility_tree(page, test_case))
                if focus.get("id") == "hidden-action":
                    break
            states["tab_sequence"] = tab_sequence
            ax_states["tab_sequence"] = ax_tab_sequence
        elif test_case == "TC07":
            page.get_by_role("button", name="Save item").click()
            page.wait_for_function("document.querySelector('#status-message').textContent.length > 0")
        elif test_case == "TC09":
            page.get_by_role("tab", name="Settings").click()
            page.wait_for_function("document.querySelector('#panel-settings').hidden === false")
            page.get_by_role("button", name="More details").click()
            page.wait_for_function("document.querySelector('#disclosure-panel').hidden === false")
        elif test_case == "TC11":
            page.locator("#focus-target").focus()
            page.get_by_role("link", name="Navigate to destination").click()
            page.get_by_role("heading", name="Destination").wait_for()
        elif test_case == "TC12":
            page.get_by_role("button", name="Open dialog").click()
            page.wait_for_function(
                """() => {
                  const dialog = document.querySelector('#research-dialog');
                  return dialog?.tagName === 'DIALOG' ? dialog.open : !dialog.hidden;
                }"""
            )
            states["dialog_open"] = {
                "active_element": _focus_state(page),
                "modal": page.locator("#research-dialog").evaluate(
                    "element => element.tagName === 'DIALOG' && element.open"
                ),
            }
            ax_states["dialog_open"] = _read_accessibility_tree(page, test_case, TC12_OPEN_TARGETS)
            page.get_by_role("button", name="Close dialog").click()
            page.wait_for_function(
                """() => {
                  const dialog = document.querySelector('#research-dialog');
                  return dialog?.tagName === 'DIALOG' ? !dialog.open : dialog.hidden;
                }"""
            )
            states["dialog_closed"] = {"active_element": _focus_state(page), "modal": False}
            ax_states["dialog_closed"] = _read_accessibility_tree(page, test_case, TC12_CLOSED_TARGETS)
        elif test_case == "TC13":
            page.locator("#focus-start").focus()
            page.keyboard.press("Tab")
            page.wait_for_function("document.activeElement?.id === 'focus-visibility'")

        states["final"] = {"active_element": _focus_state(page)}
        dom_snapshot = _dom_snapshot(page, states)
        dom_snapshot["before_interaction"] = initial_dom
        ax_states["final"] = _read_accessibility_tree(page, test_case)
        if test_case == "TC03":
            ax_states["final"]["keyboard_activation_attempted"] = (
                states.get("keyboard_activation", {}).get("activation_attempted") is True
            )
        if not isinstance(dom_snapshot.get("html"), str) or not ax_states["final"].get("nodes"):
            raise RuntimeError("The final DOM or Accessibility Tree snapshot is incomplete.")

        evidence_directory = OUTPUT_EVIDENCE / run_id / test_case / variant / access_method
        evidence_directory.mkdir(parents=True, exist_ok=True)
        stem = f"run-{run_index:02d}"
        dom_path = evidence_directory / f"{stem}.dom.json"
        ax_path = evidence_directory / f"{stem}.ax.json"
        dom_path.write_text(json.dumps(dom_snapshot, indent=2), encoding="utf-8")
        ax_path.write_text(json.dumps(ax_states, indent=2), encoding="utf-8")
        screenshot_path: str | None = None
        if test_case in {"TC13", "TC14"}:
            suffix = "focus" if test_case == "TC13" else "contrast"
            screenshot = evidence_directory / f"{stem}.{suffix}.png"
            page.screenshot(path=str(screenshot), full_page=True)
            screenshot_path = screenshot.relative_to(ROOT).as_posix()

        metadata = {
            "test_case": test_case,
            "variant": variant,
            "run_index": run_index,
            "access_method": access_method,
            "execution_status": "failed" if console_errors else "completed",
            "url": page.url,
            "page_title": page.title(),
            "console_errors": console_errors,
            "dom_evidence": dom_path.relative_to(ROOT).as_posix(),
            "ax_evidence": ax_path.relative_to(ROOT).as_posix(),
            "screenshot": screenshot_path,
        }
        return dom_snapshot, ax_states, metadata
    finally:
        context.close()


def _execution_failure(
    error: Exception,
    test_case: str,
    variant: str,
    run_index: int,
    access_method: str,
    *,
    expected: bool,
) -> dict[str, Any]:
    return {
        "test_case": test_case,
        "variant": variant,
        "run_index": run_index,
        "access_method": access_method,
        "failure_category": "capture" if expected else "unexpected",
        "error_type": type(error).__name__,
        "error": str(error),
        "traceback": traceback.format_exc(),
    }


def _git_state() -> tuple[str | None, str, str]:
    """Return the current commit, working-tree state, and an explanatory note."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
        return commit, "dirty" if dirty else "clean", ""
    except (OSError, subprocess.SubprocessError):
        return None, "unavailable", "Git is not installed or this folder is not a Git repository."


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata(browser_version: str, run_id: str) -> dict[str, Any]:
    commit, working_tree_state, commit_note = _git_state()
    return {
        "run_id": run_id,
        "experiment_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "playwright_version": version("playwright"),
        "chromium_version": browser_version,
        "operating_system": platform.platform(),
        "viewport": {"width": 1280, "height": 800},
        "locale": "en-GB",
        "git_commit": commit,
        "git_working_tree_state": working_tree_state,
        "git_commit_note": commit_note,
        "ground_truth_sha256": _sha256(GROUND_TRUTH_PATH),
        "catalogue_sha256": _sha256(CATALOGUE_PATH),
    }


def _save_outputs(run_id: str, results: list[dict[str, Any]], output_prefix: str) -> tuple[Path, Path]:
    OUTPUT_JSON.mkdir(parents=True, exist_ok=True)
    OUTPUT_CSV.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_JSON / f"{output_prefix}_{run_id}.json"
    csv_path = OUTPUT_CSV / f"{output_prefix}_{run_id}.csv"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        fields = [
            "test_case", "variant", "run_index", "engine", "criterion",
            "criterion_status", "verdict", "rule", "evidence", "execution_time",
            "access_method", "python_version", "playwright_version",
            "chromium_version", "operating_system", "git_commit",
            "git_working_tree_state", "execution_status", "dom_evidence",
            "ax_evidence", "screenshot", "sub_checks_json",
        ]
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in results:
            row = dict(item)
            row.update(item["metadata"])
            row.update(item["execution_metadata"])
            row["sub_checks_json"] = json.dumps(item.get("sub_checks", []), ensure_ascii=False)
            writer.writerow(row)
    return json_path, csv_path


def run_experiment(base_url: str, runs: int) -> tuple[Path, Path]:
    if runs != 1:
        raise ValueError("The preliminary pilot runner supports exactly one repetition.")
    catalogue = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    manual_validation_complete = ground_truth["manual_validation"]["completed"]
    mode = "pilot"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    all_results: list[dict[str, Any]] = []
    execution_failures: list[dict[str, Any]] = []
    started = time.perf_counter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        execution_metadata = _metadata(browser.version, run_id)
        try:
            for run_index in range(1, runs + 1):
                for case in catalogue["test_cases"]:
                    for variant in catalogue["variants"]:
                        for access_method in ("direct_url", "in_app_navigation"):
                            try:
                                dom, ax, metadata = _capture_variant(
                                    browser,
                                    case["id"],
                                    variant,
                                    run_index,
                                    base_url.rstrip("/"),
                                    run_id,
                                    access_method,
                                )
                            except (PlaywrightError, OSError, RuntimeError, ValueError) as error:
                                execution_failures.append(
                                    _execution_failure(
                                        error,
                                        case["id"],
                                        variant,
                                        run_index,
                                        access_method,
                                        expected=True,
                                    )
                                )
                                continue
                            except Exception as error:
                                execution_failures.append(
                                    _execution_failure(
                                        error,
                                        case["id"],
                                        variant,
                                        run_index,
                                        access_method,
                                        expected=False,
                                    )
                                )
                                continue
                            if metadata["execution_status"] == "failed":
                                execution_failures.append(
                                    {
                                        "test_case": case["id"],
                                        "variant": variant,
                                        "run_index": run_index,
                                        "access_method": access_method,
                                        "error_type": "JavaScriptPageError",
                                        "error": "; ".join(metadata["console_errors"]),
                                        "dom_evidence": metadata["dom_evidence"],
                                        "ax_evidence": metadata["ax_evidence"],
                                    }
                                )
                                continue
                            for engine, evidence in ((evaluate_dom, dom), (evaluate_ax, ax)):
                                result = engine(evidence, case["id"], variant, run_index)
                                result["access_method"] = access_method
                                result["metadata"] = metadata
                                result["execution_metadata"] = execution_metadata
                                all_results.append(result)
        finally:
            browser.close()

    output_prefix = "pilot"
    expected_attempt_count = runs * len(catalogue["test_cases"]) * len(catalogue["variants"]) * 2
    bundle = {
        "schema_version": 1,
        "study_mode": mode,
        "manual_ground_truth_validated": manual_validation_complete,
        "runs_per_variant": runs,
        "variant_count": len(catalogue["test_cases"]) * len(catalogue["variants"]),
        "navigation_methods": ["direct_url", "in_app_navigation"],
        "execution_attempt_count": expected_attempt_count,
        "completed_execution_count": expected_attempt_count - len(execution_failures),
        "execution_failures": execution_failures,
        "result_count": len(all_results),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "execution_metadata": execution_metadata,
        "ground_truth_status": ground_truth["status"],
        "catalogue_file": str(CATALOGUE_PATH.relative_to(ROOT)),
        "ground_truth_file": str(GROUND_TRUTH_PATH.relative_to(ROOT)),
        "results": all_results,
    }
    json_path, csv_path = _save_outputs(run_id, all_results, output_prefix)
    json_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return json_path, csv_path


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the SPA's paired DOM/AX accessibility experiment.")
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--runs", type=int, choices=[1], default=1)
    return parser


def main() -> None:
    parser = _argument_parser()
    args = parser.parse_args()
    json_path, csv_path = run_experiment(args.url, args.runs)
    print(f"Results JSON: {json_path}")
    print(f"Results CSV: {csv_path}")
    print("Study mode: preliminary pilot (one repetition).")
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"Browser execution failures: {len(bundle['execution_failures'])}")


if __name__ == "__main__":
    main()
