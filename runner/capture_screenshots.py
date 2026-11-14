from __future__ import annotations

import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "screenshots"
REPORTS = ROOT / "reports" / "json"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    analysis_files = sorted(REPORTS.glob("analysis_*.json"), key=lambda path: path.stat().st_mtime)
    analysis = json.loads(analysis_files[-1].read_text(encoding="utf-8")) if analysis_files else None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900}, locale="en-GB")
        page.goto("http://127.0.0.1:5000", wait_until="networkidle")
        page.wait_for_selector('html[data-app-ready="true"]')
        page.screenshot(path=str(OUTPUT / "dashboard.png"), full_page=True)
        page.goto("http://127.0.0.1:5000/#/case/TC01/conforming", wait_until="networkidle")
        page.wait_for_selector('[data-test-case="TC01"]')
        page.screenshot(path=str(OUTPUT / "tc01-conforming.png"), full_page=True)
        page.goto("http://127.0.0.1:5000/#/case/TC13/conforming", wait_until="networkidle")
        page.wait_for_selector('[data-test-case="TC13"]')
        page.locator("#focus-start").focus()
        page.keyboard.press("Tab")
        page.wait_for_function("document.activeElement?.id === 'focus-visibility'")
        page.screenshot(path=str(OUTPUT / "tc13-keyboard-focus.png"), full_page=True)
        page.goto("http://127.0.0.1:5000/#/case/TC14/conforming", wait_until="networkidle")
        page.wait_for_selector('[data-test-case="TC14"]')
        page.screenshot(path=str(OUTPUT / "tc14-text-contrast.png"), full_page=True)
        if analysis is not None:
            escaped = html.escape(json.dumps(analysis, indent=2))
            page.set_content(
                f"""<!doctype html>
                <html lang="en"><head><meta charset="utf-8"><title>Experiment analysis output</title>
                <style>
                  body {{ margin: 0; padding: 2rem; color: #172033; background: #f4f6fb; font: 16px system-ui, sans-serif; }}
                  main {{ max-width: 76rem; margin: auto; padding: 2rem; background: white; border: 1px solid #d6dbea; border-radius: .75rem; }}
                  pre {{ max-height: 65vh; overflow: auto; padding: 1rem; background: #f5f7fb; font-size: 12px; }}
                </style></head><body><main><h1>Experiment analysis output</h1>
                <p>Run: {html.escape(analysis["run_id"])}</p>
                <p>Study status: {html.escape(analysis["study_mode"])}</p>
                <p>Variant-level agreement: {html.escape(str(analysis["agreement"]["all_classifiable_variants"]["agreement_rate"]))}</p>
                <pre>{escaped}</pre></main></body></html>"""
            )
            page.screenshot(path=str(OUTPUT / "analysis-output.png"), full_page=True)
        browser.close()
    print(f"Screenshots saved under {OUTPUT}")


if __name__ == "__main__":
    main()
