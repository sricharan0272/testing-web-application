from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "screenshots"
def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
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
        browser.close()
    print(f"Screenshots saved under {OUTPUT}")


if __name__ == "__main__":
    main()
