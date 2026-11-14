from __future__ import annotations

import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from engines.results import build_result

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = json.loads((ROOT / "testcases" / "catalogue.json").read_text(encoding="utf-8"))
CASE_BY_ID = {case["id"]: case for case in CATALOGUE["test_cases"]}
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class _ElementParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = {
            "index": len(self.elements),
            "tag": tag.lower(),
            "attrs": {key.lower(): value for key, value in attrs},
            "text": "",
            "parent": self._stack[-1]["index"] if self._stack else None,
        }
        self.elements.append(element)
        if tag.lower() not in VOID_ELEMENTS:
            self._stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_ELEMENTS and self._stack:
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index]["tag"] == tag.lower():
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1]["text"] += data


def _dom_elements(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    parser = _ElementParser()
    parser.feed(snapshot.get("html", ""))
    elements = parser.elements
    for shadow_root in snapshot.get("shadow_roots", []):
        shadow_parser = _ElementParser()
        shadow_parser.feed(shadow_root.get("html", ""))
        offset = len(elements)
        for element in shadow_parser.elements:
            element["index"] += offset
            if element["parent"] is not None:
                element["parent"] += offset
        elements.extend(shadow_parser.elements)
    return elements


def _descendant_text(element: dict[str, Any], elements: list[dict[str, Any]]) -> str:
    parts = [element["text"]]
    for child in elements:
        if child["parent"] == element["index"]:
            parts.append(_descendant_text(child, elements))
    return " ".join(part.strip() for part in parts if part.strip()).strip()


def _elements_with_id(elements: list[dict[str, Any]], element_id: str) -> list[dict[str, Any]]:
    return [item for item in elements if item["attrs"].get("id") == element_id]


def _is_hidden_by_aria(element: dict[str, Any], elements: list[dict[str, Any]]) -> bool:
    by_index = {item["index"]: item for item in elements}
    current: int | None = element["index"]
    while current is not None and current in by_index:
        ancestor = by_index[current]
        if (ancestor["attrs"].get("aria-hidden") or "").lower() == "true":
            return True
        current = ancestor["parent"]
    return False


def evaluate(snapshot: dict[str, Any], test_case: str, variant: str, run_index: int = 0) -> dict[str, Any]:
    started = time.perf_counter()
    if test_case not in CASE_BY_ID:
        raise ValueError(f"Unknown test case: {test_case}")
    case = CASE_BY_ID[test_case]
    if not isinstance(snapshot.get("html", ""), str):
        return build_result(
            test_case=test_case,
            variant=variant,
            engine="DOM",
            criterion=case["criterion"],
            criterion_status=case["mapping_status"],
            verdict="NOT_TESTABLE",
            rule="invalid_dom_evidence",
            evidence="The DOM snapshot does not contain an HTML string.",
            execution_time=time.perf_counter() - started,
            run_index=run_index,
        )
    elements = _dom_elements(snapshot)
    verdict = "NOT_TESTABLE"
    rule = "unsupported_case"
    evidence = "DOM rule is not defined for this case."
    interaction = snapshot.get("interaction_states", {})
    if not isinstance(interaction, dict):
        interaction = {}
    sub_checks: list[dict[str, Any]] = []

    if test_case == "TC01":
        targets = [item for item in elements if item["attrs"].get("data-test-image") == "informative"]
        rule = "informative_image_nonempty_alt_attribute"
        if len(targets) != 1:
            verdict = "NOT_TESTABLE"
            evidence = f"Expected exactly one informative image target; found {len(targets)}."
        else:
            alternative = targets[0]["attrs"].get("alt")
            generic_alternatives = {"image", "picture", "photo", "graphic", "icon", "illustration"}
            normalized_alternative = (alternative or "").strip().casefold()
            if alternative is None or not normalized_alternative:
                verdict = "FAIL"
            elif normalized_alternative in generic_alternatives:
                verdict = "NOT_TESTABLE"
            else:
                verdict = "PASS"
            evidence = (
                f"Informative image alt={alternative!r}; non-empty and non-generic text is "
                "checked mechanically, but accuracy and usefulness require human review."
            )
    elif test_case == "TC02":
        fields = [item for item in elements if item["attrs"].get("id") == "email"]
        labels = [item for item in elements if item["tag"] == "label" and item["attrs"].get("for") == "email"]
        rule = "label_for_reference"
        if len(fields) != 1:
            verdict = "NOT_TESTABLE"
            evidence = f"Expected exactly one email target field; found {len(fields)}."
        else:
            associated = fields[0]["tag"] in {"input", "select", "textarea"} and bool(labels)
            verdict = "PASS" if associated else "FAIL"
            evidence = f"Target #email is a form control={fields[0]['tag'] in {'input', 'select', 'textarea'}}; matching label reference count={len(labels)}."
    elif test_case == "TC03":
        controls = _elements_with_id(elements, "custom-action")
        control = controls[0] if len(controls) == 1 else None
        if control is not None:
            is_button = control["tag"] == "button" or control["attrs"].get("role") == "button"
            name = (control["attrs"].get("aria-label") or _descendant_text(control, elements)).strip()
            verdict = "PASS" if is_button and name == "Run test" else "FAIL"
            rule = "button_role_and_name"
            evidence = f"Target role is button={is_button}; DOM-derived name={name!r}; expected 'Run test'."
            activation = interaction.get("keyboard_activation")
            activation_count = control["attrs"].get("data-activated")
            sub_checks.append(
                {
                    "assertion": "sequential keyboard focusability",
                    "criterion": "2.1.1",
                    "verdict": (
                        "NOT_TESTABLE"
                        if not isinstance(activation, dict) or activation.get("tab_sequence_attempted") is not True
                        else ("PASS" if activation.get("target_focused_by_tab") is True else "FAIL")
                    ),
                    "rule": "sequential_tab_reaches_control",
                    "evidence": (
                        f"Sequential Tab attempted={activation.get('tab_sequence_attempted') if isinstance(activation, dict) else None}; "
                        f"target reached={activation.get('target_focused_by_tab') if isinstance(activation, dict) else None}."
                    ),
                }
            )
            sub_checks.append(
                {
                    "assertion": "Enter/Space activation after focus",
                    "criterion": "2.1.1",
                    "verdict": (
                        "NOT_TESTABLE"
                        if not isinstance(activation, dict) or activation.get("activation_attempted") is not True
                        else ("PASS" if activation_count == "2" else "FAIL")
                    ),
                    "rule": "enter_space_activation_after_focus",
                    "evidence": (
                        f"Target reached by Tab={activation.get('target_focused_by_tab') if isinstance(activation, dict) else None}; "
                        f"Enter/Space dispatched={activation.get('activation_attempted') if isinstance(activation, dict) else None}; "
                        f"DOM activation counter={activation_count!r}."
                    ),
                }
            )
    elif test_case == "TC04":
        buttons = _elements_with_id(elements, "search-action")
        button = buttons[0] if len(buttons) == 1 else None
        if button is not None:
            visible = _descendant_text(button, elements).casefold()
            name = (button["attrs"].get("aria-label") or visible).casefold()
            verdict = "PASS" if visible and visible in name else "FAIL"
            rule = "label_in_aria_label"
            evidence = f"Visible label={visible!r}; DOM label/name source={name!r}."
    elif test_case == "TC05":
        targets = [item for item in elements if item["attrs"].get("id") == "hidden-action"]
        tab_sequence = interaction.get("tab_sequence")
        rule = "fixture_target_in_tab_sequence_and_aria_hidden"
        if len(targets) != 1 or not isinstance(tab_sequence, list):
            verdict = "NOT_TESTABLE"
            evidence = (
                f"Expected one #hidden-action target and a recorded tab sequence; "
                f"targets={len(targets)}, tab sequence available={isinstance(tab_sequence, list)}."
            )
        else:
            reached_by_tab = any(
                isinstance(item, dict) and item.get("id") == "hidden-action"
                for item in tab_sequence
            )
            hidden = _is_hidden_by_aria(targets[0], elements) or (
                targets[0]["attrs"].get("aria-hidden") or ""
            ).lower() == "true"
            verdict = "FAIL" if reached_by_tab and hidden else "PASS"
            evidence = (
                f"Target reached by sequential Tab={reached_by_tab}; target hidden from accessibility "
                f"semantics by aria-hidden={hidden}. This is a fixture-specific check, not full ACT-rule coverage."
            )
    elif test_case == "TC06":
        shadow_parser_elements = []
        for root in snapshot.get("shadow_roots", []):
            parser = _ElementParser()
            parser.feed(root.get("html", ""))
            shadow_parser_elements.extend(parser.elements)
        buttons = [item for item in shadow_parser_elements if item["attrs"].get("id") == "shadow-action"]
        if len(buttons) != 1:
            verdict = "NOT_TESTABLE"
            rule = "shadow_button_accessible_name_proxy"
            evidence = f"Expected exactly one mapped shadow button; found {len(buttons)}."
        else:
            target = buttons[0]
            has_name = bool((target["attrs"].get("aria-label") or _descendant_text(target, shadow_parser_elements)).strip())
            verdict = "PASS" if target["tag"] == "button" and has_name else "FAIL"
            rule = "shadow_button_accessible_name_proxy"
            evidence = f"Mapped shadow button has native button semantics={target['tag'] == 'button'}; text alternative present={has_name}."
    elif test_case == "TC07":
        statuses = _elements_with_id(elements, "status-message")
        status = statuses[0] if len(statuses) == 1 else None
        if status is not None:
            has_live_semantics = status["attrs"].get("role") == "status" or status["attrs"].get("aria-live") in {"polite", "assertive"}
            has_message = bool(_descendant_text(status, elements))
            verdict = "PASS" if has_live_semantics and has_message else "FAIL"
            rule = "dynamic_status_semantics"
            evidence = f"Updated message present={has_message}; status/live semantics={has_live_semantics}."
    elif test_case == "TC08":
        fields = _elements_with_id(elements, "account-email")
        field = fields[0] if len(fields) == 1 else None
        reference = field["attrs"].get("aria-describedby") if field else None
        verdict = "NOT_TESTABLE"
        rule = "error_association_observation"
        evidence = f"aria-describedby={reference!r}; association alone does not establish a WCAG 3.3.1 failure."
    elif test_case == "TC09":
        tabs = _elements_with_id(elements, "tab-settings")
        panels = _elements_with_id(elements, "panel-settings")
        tab = tabs[0] if len(tabs) == 1 else None
        panel = panels[0] if len(panels) == 1 else None
        if tab is not None and panel is not None:
            selected = tab["attrs"].get("aria-selected") == "true"
            visible = "hidden" not in panel["attrs"]
            verdict = "PASS" if selected and visible else "FAIL"
            rule = "selected_state_after_activation"
            evidence = f"Settings aria-selected={selected}; panel visible={visible}."
            disclosures = _elements_with_id(elements, "disclosure")
            disclosure_panels = _elements_with_id(elements, "disclosure-panel")
            disclosure = disclosures[0] if len(disclosures) == 1 else None
            disclosure_panel = disclosure_panels[0] if len(disclosure_panels) == 1 else None
            if disclosure is not None and disclosure_panel is not None:
                expanded = disclosure["attrs"].get("aria-expanded") == "true"
                disclosure_visible = "hidden" not in disclosure_panel["attrs"]
                sub_checks.append(
                    {
                        "assertion": "expanded state on activated disclosure",
                        "criterion": "4.1.2",
                        "verdict": "PASS" if expanded and disclosure_visible else "FAIL",
                        "rule": "disclosure_expanded_state",
                        "evidence": f"aria-expanded={expanded}; controlled panel visible={disclosure_visible}.",
                    }
                )
    elif test_case == "TC10":
        title_matches = re.findall(r"<title[^>]*>(.*?)</title>", snapshot["html"], flags=re.IGNORECASE | re.DOTALL)
        title = re.sub(r"\s+", " ", title_matches[0]).strip() if len(title_matches) == 1 else ""
        verdict = "NOT_TESTABLE" if len(title_matches) != 1 else ("PASS" if "reports" in title.casefold() else "FAIL")
        rule = "document_title_identifies_route"
        evidence = f"Found {len(title_matches)} title element(s); title={title!r}; expected it to identify Reports."
    elif test_case == "TC11":
        final_state = interaction.get("final")
        active = final_state.get("active_element") if isinstance(final_state, dict) else None
        verdict = "NOT_TESTABLE" if not isinstance(active, dict) else ("PASS" if active.get("id") == "main-content" else "FAIL")
        rule = "focus_after_route_change_observation"
        evidence = f"Focused DOM element after route replacement: {active.get('tag')}#{active.get('id')}." if isinstance(active, dict) else "Final active-element evidence is missing."
    elif test_case == "TC12":
        opened = interaction.get("dialog_open", {})
        closed = interaction.get("dialog_closed", {})
        opened_active = opened.get("active_element") if isinstance(opened, dict) else None
        closed_active = closed.get("active_element") if isinstance(closed, dict) else None
        if not isinstance(opened, dict) or not isinstance(closed, dict) or not opened or not closed:
            verdict = "NOT_TESTABLE"
        else:
            if not isinstance(opened_active, dict) or not isinstance(closed_active, dict):
                verdict = "NOT_TESTABLE"
            else:
                entry_ok = opened_active.get("id") == "dialog-close"
                return_ok = closed_active.get("id") == "dialog-opener"
                verdict = "PASS" if entry_ok and return_ok and opened.get("modal") else "FAIL"
        rule = "dialog_focus_entry_and_return_observation"
        evidence = (
            f"Focus entered dialog={opened_active.get('id') == 'dialog-close'}; "
            f"focus restored to opener={closed_active.get('id') == 'dialog-opener'}; "
            f"modal={opened.get('modal')}."
            if isinstance(opened_active, dict) and isinstance(closed_active, dict) and isinstance(opened, dict)
            else "Dialog-open and dialog-closed interaction evidence is required."
        )
    elif test_case == "TC13":
        verdict = "NOT_TESTABLE"
        rule = "rendered_focus_indicator_outside_structural_evidence"
        evidence = "DOM structure alone cannot establish whether a focus indicator is visibly rendered."
    elif test_case == "TC14":
        verdict = "NOT_TESTABLE"
        rule = "rendered_text_contrast_outside_structural_evidence"
        evidence = "DOM structure alone cannot establish rendered foreground/background colors or their contrast ratio."

    elapsed = time.perf_counter() - started
    return build_result(
        test_case=test_case,
        variant=variant,
        engine="DOM",
        criterion=case["criterion"],
        criterion_status=case["mapping_status"],
        verdict=verdict,
        rule=rule,
        evidence=evidence,
        execution_time=elapsed,
        run_index=run_index,
        sub_checks=sub_checks,
    )
