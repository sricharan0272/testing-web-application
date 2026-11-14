import argparse
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "smoke" / "dom_snapshot.html"


def main():
    parser = argparse.ArgumentParser(description="Capture rendered DOM from the research SPA.")
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800}, locale="en-GB")
        page.goto(args.url, wait_until="networkidle")
        page.wait_for_selector('html[data-app-ready="true"]')
        rendered_html = page.content()
        args.output.write_text(rendered_html, encoding="utf-8")

        metadata_path = args.output.with_suffix(".json")
        metadata_path.write_text(
            json.dumps(
                {
                    "url": page.url,
                    "title": page.title(),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "playwright_version": version("playwright"),
                    "browser_version": browser.version,
                    "output_file": str(args.output),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Rendered DOM saved to {args.output}")
        print(f"Capture metadata saved to {metadata_path}")
        browser.close()


if __name__ == "__main__":
    main()
