import argparse
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "smoke" / "accessibility_tree.json"


def main():
    parser = argparse.ArgumentParser(
        description="Capture Chromium's full Accessibility Tree through CDP."
    )
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800}, locale="en-GB")
        page.goto(args.url, wait_until="networkidle")
        page.wait_for_selector('html[data-app-ready="true"]')
        cdp = page.context.new_cdp_session(page)
        tree = cdp.send("Accessibility.getFullAXTree")

        capture = {
            "url": page.url,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "playwright_version": version("playwright"),
            "browser_version": browser.version,
            "method": "Chrome DevTools Protocol Accessibility.getFullAXTree",
            "node_count": len(tree["nodes"]),
            "nodes": tree["nodes"],
        }
        args.output.write_text(json.dumps(capture, indent=2), encoding="utf-8")
        print(f"Captured {capture['node_count']} Accessibility Tree nodes to {args.output}")
        browser.close()


if __name__ == "__main__":
    main()
