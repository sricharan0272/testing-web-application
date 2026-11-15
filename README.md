# Accessibility Testing Web Application

A Flask single page application and browser test bed for comparing automated accessibility checks that use rendered DOM evidence with checks that use Chromium's computed Accessibility Tree.

## Implemented scope

The project includes a literature and WCAG review, 14 test cases with 28 conforming/defective variants, a Flask dashboard and SPA routes, DOM and Accessibility Tree engines, Playwright/CDP evidence capture with scripted interactions, automated implementation tests, application screenshots, and a one-repetition pilot across direct URL and in-app navigation. The pilot stores JSON/CSV results and browser evidence. Expected outcomes remain provisional pending human validation.

The project is research infrastructure, not a general accessibility checker or a declaration of overall WCAG conformance. TC13 and TC14 require rendering judgment, so the structural engines return `NOT_TESTABLE` and screenshots are retained as reviewer evidence. A static live-region snapshot cannot establish that a screen reader announced an update.

Expected outcomes are predeclared in `testcases/ground_truth.json`. Manual validation is incomplete and the reference has not been frozen against a Git baseline. Do not present expected outcomes as validated ground truth. Mapping rationales and source links are in `testcases/mapping_review.md`.

## Technology and structure

- Python 3.10+, Flask, HTML/CSS/JavaScript
- Playwright for Python, Chromium and Chrome DevTools Protocol
- JSON, CSV and pytest

```text
app/                         Flask SPA, dashboard, routes and fixtures
engines/                     DOM and Accessibility Tree engines
runner/                      Browser automation, evidence capture and pilot runner
testcases/                   14 cases, 28 specifications and provisional references
tests/                       Implementation and application verification
reports/screenshots/         Application screenshots
reports/smoke/               Initial DOM and Accessibility Tree captures
reports/json, reports/csv/    One-repetition pilot results
reports/evidence/            Pilot DOM and Accessibility Tree evidence
analysis/pilot_summary.py    Descriptive summary for pilot results
docs/REVIEW_AND_TODO.md      Planned work beyond the current implementation
```

## Install on Windows PowerShell

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Run the application and capture evidence

Start Flask:

```powershell
.\.venv\Scripts\python.exe app\app.py
```

Open `http://127.0.0.1:5000`. The dashboard links to case variants. Regenerate case specifications and screenshots while Flask is running:

```powershell
.\.venv\Scripts\python.exe -m testcases.generate_specs
.\.venv\Scripts\python.exe runner\capture_screenshots.py
```

Initial smoke captures can be made with:

```powershell
.\.venv\Scripts\python.exe runner\playwright_runner.py
.\.venv\Scripts\python.exe runner\cdp_capture.py
```

## Run the preliminary pilot

With Flask running in another terminal:

```powershell
.\.venv\Scripts\python.exe -m runner.experiment_runner
```

The runner accepts exactly one repetition. It exercises all 28 variants by direct URL and in-app navigation, performs scripted interactions, captures DOM and Accessibility Tree evidence, evaluates both engines, and writes JSON/CSV output. A complete run has 112 engine results (28 variants x 2 navigation methods x 1 repetition x 2 engines), excluding failed executions.

Summarize a pilot bundle:

```powershell
.\.venv\Scripts\python.exe -m analysis.pilot_summary reports\json\pilot_<run-id>.json
```

The descriptive summary reports variants, captures, engine verdict counts, and execution failures. Runs are labeled as pilots while manual validation is pending.

## Implementation verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Future work

Independent manual validation, a Git baseline and reference freeze, a ten-repetition confirmatory experiment, full statistical analysis and paired hypothesis testing, detailed disagreement interpretation, final evaluation and conclusions, a final report, and clean-environment reproduction are planned. These items are not implemented in the current project. See `docs/REVIEW_AND_TODO.md`.
