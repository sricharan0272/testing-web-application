# Project status and future work

## Implemented

- Literature and WCAG review with documented criterion mappings.
- Flask single page application, dashboard, routes, and conforming/defective examples.
- Fourteen test cases represented by 28 variants.
- Independent DOM and Chromium Accessibility Tree engines.
- Playwright automation, CDP Accessibility Tree capture, scripted interactions, and browser evidence.
- Automated implementation tests, application checks, and evidence screenshots.
- Preliminary pilot with one repetition under direct URL and in-app navigation, JSON/CSV results, and a descriptive summary.

## Future work

- Establish a Git baseline and verify/freeze the expected reference before confirmatory work.
- Complete independent manual validation of all 28 variants. Until then, expected outcomes remain provisional.
- Run the ten-repetition confirmatory experiment after reference validation.
- Perform full statistical analysis and paired hypothesis testing.
- Interpret disagreements using the captured evidence.
- Complete final evaluation, conclusions, and the final report.
- Reproduce the workflow in a clean environment.

The two one-repetition pilot bundles and their browser evidence remain in `reports/`. Later-stage analysis code and ten-repetition results have been removed from the project. Their associated evaluation tasks remain listed above as future work.

## Current limits

- The ground-truth record states that manual validation is incomplete and the reference freeze is unverified. These statuses must only change when the corresponding work is actually completed and recorded.
- TC13 and TC14 require visual review; structural engines return `NOT_TESTABLE` for those rendering judgments.
- A static live-region snapshot cannot establish screen-reader announcement behavior.
- The controlled fixtures do not estimate general web accessibility performance.
