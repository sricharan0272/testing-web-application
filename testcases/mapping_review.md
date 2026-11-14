# WCAG mapping review

The rule verdicts are narrow checks on the fixture assertions, not evaluations
of an entire page's WCAG conformance. WCAG describes success criteria; HTML
attributes and testing techniques are evidence, not automatic compliance
proofs.

| Case | Proposed criterion | Mapping decision |
|---|---|---|
| TC01 | 1.1.1 Non-text Content | Confirmed for the informative image. The control checks meaningful text-alt presence only as an operational proxy; a human must judge whether the text serves the image's equivalent purpose. Both variants include an empty alternative on a separate decorative image. |
| TC02 | 1.3.1 Info and Relationships | Confirmed for the broken visible-label/control relationship. The placeholder is not used as evidence that the visible relationship exists. **3.3.2 is not treated as failed:** visible label text exists in both variants; the fixture does not test omission of labels/instructions. |
| TC03 | 4.1.2 Name, Role, Value; 2.1.1 Keyboard | Separate assertions. The primary check concerns the custom control's exposed name/role semantics. The secondary check sends Enter and Space and looks for the resulting action. Keyboard operability is not inferred just from the element role. |
| TC04 | 2.5.3 Label in Name | Confirmed for the adjacent visible button text `Search` and the computed/declared name. The defect's name `Find` omits the visible text. |
| TC05 | 4.1.2; ACT rule 6cfa84 | The ACT rule specifically concerns sequential-focus descendants of `aria-hidden="true"` and maps failed outcomes to 4.1.2. The DOM engine can inspect ancestry. The AX engine returns `NOT_TESTABLE` where the captured tree cannot establish that ancestry; it does not guess from the button's presence or focusability alone. |
| TC06 | 4.1.2 Name, Role, Value | Confirmed as a narrow missing-computed-name proxy for the button in the open shadow root. A nonempty name still needs human review for whether it is meaningful. |
| TC07 | 4.1.3 Status Messages | Confirmed for a dynamically added success message that does not take focus. The automated rule tests the exposed status/live semantics after update. Only a screen-reader test can establish actual announcement behavior for the chosen browser/AT combination. |
| TC08 | 3.3.1 Error Identification | Criterion verdict is `NOT_TESTABLE` for this pairing. WCAG 3.3.1 requires an automatically detected input error to be identified and described in text; the fixture has visible error text. Missing `aria-describedby` is only an association observation and is not, by itself, a 3.3.1 failure. Programmatic relationships may instead be relevant to 1.3.1/4.1.2 depending on the exact behavior. |
| TC09 | 4.1.2 Name, Role, Value | Separate state assertions check the active tab's selected state and the activated disclosure's expanded state after interaction. The active panel is also observed, but is not a substitute for checking the state exposed to AT. |
| TC10 | 2.4.2 Page Titled | Confirmed. WCAG's Understanding document explicitly covers dynamic SPA views and says the title should change to identify the current view/topic. |
| TC11 | 2.4.3 Focus Order | Interpretive observation only. The rule measures focus after replacing the route content. A move of focus to body alone does not establish that the sequence affected meaning/operation or that the criterion failed. |
| TC12 | 2.4.3 Focus Order | Interpretive observation only. The fixture records focus entry, modality, and return after close. WCAG's examples describe focus handling in modal dialogs, but a specific failure needs to be judged in the actual focus sequence and user flow. |
| TC13 | 2.4.7 Focus Visible | Extension requiring visual evidence. The criterion requires a visible indicator in a mode of operation; computed outline style is only a proxy. The saved screenshot and keyboard procedure require human review. |
| TC14 | 1.4.3 Contrast (Minimum) | Extension requiring rendered-color review. The WCAG threshold is 4.5:1 for normal text, subject to criterion exceptions. This fixture uses opaque solid colors and normal-size text; computed-style contrast is not a general-purpose background-rendering solution. |

## Authoritative W3C sources

- [WCAG 2.2 Understanding 1.1.1 — Non-text Content](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html)
- [WCAG 2.2 Understanding 1.3.1 — Info and Relationships](https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships.html)
- [WCAG 2.2 Understanding 2.1.1 — Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html)
- [WCAG 2.2 Understanding 2.4.2 — Page Titled](https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html)
- [WCAG 2.2 Understanding 2.4.3 — Focus Order](https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html)
- [WCAG 2.2 Understanding 2.4.7 — Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html)
- [WCAG 2.2 Understanding 2.5.3 — Label in Name](https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html)
- [WCAG 2.2 Understanding 3.3.1 — Error Identification](https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html)
- [WCAG 2.2 Understanding 3.3.2 — Labels or Instructions](https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html)
- [WCAG 2.2 Understanding 4.1.2 — Name, Role, Value](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html)
- [WCAG 2.2 Understanding 4.1.3 — Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)
- [WCAG 2.2 Understanding 1.4.3 — Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- [ACT rule 6cfa84 — Element with aria-hidden has no content in sequential focus navigation](https://www.w3.org/WAI/standards-guidelines/act/rules/6cfa84/)

The source mappings are reviewed; completion of independent empirical
validation remains pending in `ground_truth.json`.
