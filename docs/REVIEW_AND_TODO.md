# Project review and submission checklist

Reviewed against the current workspace and the proposal notes. The current build is a Flask-based accessibility research lab that captures DOM and Accessibility Tree evidence across controlled fixture variants.

## Remaining work before final validation

| # | Task | Why it matters | Effort |
|---|---|---|---|
| 1 | Complete `testcases/manual_validation_template.csv` using the approved protocol (keyboard, screen reader, and browser Accessibility pane evidence). Do not mark validation complete unless the review genuinely happened. | The expected outcomes remain provisional until human review is recorded. | 1-2 days |
| 2 | Establish Git history when Git is available, commit and tag the reviewed source/reference, and run the confirmatory experiment only after the reference is approved. | The current workspace has no Git repository, so the pilot manifest cannot identify a commit. | 1 hour |
| 3 | Write the final report (method, results, discussion, limitations, and references), separate from the generated summary in `reports/research_report.md`. | The generated report is a results summary, not the final submission document. | 3-5 days |
| 4 | Confirm the final analysis artifacts and screenshots match the confirmatory run before submission. | The project includes historical pilots that must remain clearly identified. | 30 min |

## Key caveats

1. Ground truth is predeclared but unvalidated until an independent human reviewer completes the manual-validation row set.
2. The fixture set is purpose-built and does not estimate general web accessibility performance beyond the controlled cases.
3. TC08, TC11, TC12, TC13, and TC14 require careful interpretive or visual review; the structural engines intentionally do not claim universal correctness here.
4. Navigation-dependent verdicts are treated as unstable and excluded from aggregate variant conclusions when they vary across direct URL and in-app navigation.
5. Historical pilot runs should remain distinct from any future confirmatory run; keep run IDs and evidence separate.

## Current verification status

- The local test suite is passing for the current project configuration.
- Browser capture and analysis runs are reproducible within the recorded pilot runs.
- Ground truth remains provisional until independent reviewer evidence is added and the confirmatory run is completed.

## Final pre-submission checklist

- [ ] Human validation completed and recorded with evidence
- [ ] Git history established and working tree clean at the confirmatory run
- [ ] Confirmatory experiment regenerated from the approved reference
- [ ] Analysis numbers match the final CSV/JSON bundle
- [ ] Final report cites the relevant WCAG/ACT sources and the project limitations
- [ ] Final validation claim is limited to the recorded human-review evidence and the captured experiment results
