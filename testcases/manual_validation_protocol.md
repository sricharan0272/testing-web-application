# Human manual validation protocol

## Status

Human validation has not been completed yet. The project proposal (section 4.3)
says the study author confirms ground truth with a keyboard-only check, a screen
reader (NVDA or VoiceOver) and the browser Accessibility pane, keeping notes and
screenshots, and discusses ambiguous cases with the supervisor. This protocol
therefore supports **author validation** (record `reviewer` as the author and
call it author-validated, not independent) and, preferably, a second person
re-checking a sample of rows. The reference outcomes in `ground_truth.json` stay
provisional until the CSV is completed.

## Independence and blinding

The reviewer must complete the included CSV without consulting
`ground_truth.json`, engine results, disagreement reports, or the research
report. The current SPA route names include `conforming` and `defective`, so
this procedure is **not fully blinded**. Record this limitation; do not claim a
blinded review.

## Setup

1. Use the same supported Chromium browser and 1280 × 800 viewport recorded
   for the pilot. Record the browser and version, operating system, date, and
   screen-reader/AT name and version (or `not used`).
2. Start the Flask app from the project root:

   ```powershell
   .\.venv\Scripts\python.exe app\app.py
   ```

3. Open each route listed in `manual_validation_template.csv`. Complete the
   recorded task for that case and variant. Reload between variants.
4. For keyboard checks, use only the keyboard for the tested operation and
   record the focused element and observed visual focus indicator.
5. For screen-reader checks, record the spoken output and whether it occurred
   after the tested interaction. A computed role or live-region property is
   not evidence that an announcement was actually made.
6. For TC13 and TC14, save a screenshot of the rendered state. For TC14, record
   the measured foreground/background colors, contrast ratio, text size/weight,
   opacity, and any applicable exception considered.

## Recording decisions

Complete one row per variant. Do not copy the existing expected verdict into
the form.

- `PASS`: the observed fixture meets the narrowly stated assertion.
- `FAIL`: the observed fixture does not meet that assertion.
- `INAPPLICABLE`: the criterion does not apply to the observed content/state.
- `NOT_TESTABLE`: available observations cannot settle the assertion.

Record a separate criterion-level judgment where the criterion is interpretive
(especially TC11 and TC12). Keep observable behavior distinct from a conclusion
that a WCAG criterion is failed. For TC08, do not treat a missing
`aria-describedby` association alone as a 3.3.1 failure. For TC01, judge whether
the alternative text conveys the informative image's purpose, not just whether
an `alt` attribute exists.

For every decision, enter concise evidence and a rationale. Use a file path for
each saved screenshot, recording, or other evidence. If the browser/AT
combination cannot provide evidence, state that explicitly and use
`NOT_TESTABLE` where appropriate.

## Completion and adjudication

1. The independent reviewer returns the completed CSV and evidence to the
   study owner.
2. The study owner compares the review with the predeclared reference only
   after the reviewer has completed and saved an independent copy.
3. Resolve disagreements with a documented discussion or a third adjudicator;
   preserve each initial rating and the final rationale.
4. Update `ground_truth.json` only after review. Record reviewer, completion
   date, evidence paths, unresolved items, and adjudication. Never turn
   unperformed checks into completed observations.
5. Re-run the experiment as a confirmatory run only after the reference
   outcomes are adjudicated. Preserve the existing pilot unchanged.

