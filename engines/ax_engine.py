from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from engines.results import build_result

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = json.loads((ROOT / "testcases" / "catalogue.json").read_text(encoding="utf-8"))
CASE_BY_ID = {case["id"]: case for case in CATALOGUE["test_cases"]}


def _value(value: Any) -> Any:
    return value.get("value") if isinstance(value, dict) else value


def _nodes(evidence: dict[str, Any], state: str = "final") -> list[dict[str, Any]]:
    state_data = evidence.get(state, {})
    if isinstance(state_data, list):
        return state_data
    return state_data.get("nodes", []) if isinstance(state_data, dict) else []


def _role(node: dict[str, Any]) -> str:
    return str(_value(node.get("role", "")))


def _name(node: dict[str, Any]) -> str:
    return str(_value(node.get("name", "")) or "")


def _properties(node: dict[str, Any]) -> dict[str, Any]:
    return {item["name"]: _value(item.get("value")) for item in node.get("properties", [])}


def _target_node(
    evidence: dict[str, Any],
    nodes: list[dict[str, Any]],
    target: str = "primary",
) -> dict[str, Any] | None:
    target_ids = evidence.get("target_backend_node_ids")
    if not isinstance(target_ids, dict):
        final_state = evidence.get("final")
        target_ids = final_state.get("target_backend_node_ids") if isinstance(final_state, dict) else None
    if not isinstance(target_ids, dict):
        return None
    backend_node_id = target_ids.get(target)
    if backend_node_id is None:
        return None
    matches = [node for node in nodes if node.get("backendDOMNodeId") == backend_node_id]
    return matches[0] if len(matches) == 1 else None


def _child_names(node: dict[str, Any], nodes: list[dict[str, Any]]) -> list[str]:
    by_id = {item.get("nodeId"): item for item in nodes}
    return [
        _name(by_id[child_id])
        for child_id in node.get("childIds", [])
        if child_id in by_id and _name(by_id[child_id])
    ]


def _descendant_text(node: dict[str, Any], nodes: list[dict[str, Any]]) -> str:
    by_id = {item.get("nodeId"): item for item in nodes}
    names = []
    pending = list(node.get("childIds", []))
    visited = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited or child_id not in by_id:
            continue
        visited.add(child_id)
        child = by_id[child_id]
        if _name(child):
            names.append(_name(child))
        pending.extend(child.get("childIds", []))
    return " ".join(names)


def evaluate(evidence: dict[str, Any], test_case: str, variant: str, run_index: int = 0) -> dict[str, Any]:
    started = time.perf_counter()
    if test_case not in CASE_BY_ID:
        raise ValueError(f"Unknown test case: {test_case}")
    case = CASE_BY_ID[test_case]
    nodes = _nodes(evidence)
    verdict = "NOT_TESTABLE"
    rule = "unsupported_ax_case"
    detail = "The Accessibility Tree evidence does not expose a decision-relevant property."
    sub_checks: list[dict[str, Any]] = []
    evidence_nodes: list[dict[str, Any]] = []

    if test_case == "TC01":
        image = _target_node(evidence, nodes)
        if image is None:
            detail = "The uniquely mapped informative-image node is missing from the Accessibility Tree evidence."
        else:
            evidence_nodes.append(image)
            image_name = _name(image).strip()
            if _role(image) != "image" or image.get("ignored", False) or not image_name:
                verdict = "FAIL"
            elif image_name.casefold() in {"image", "picture", "photo", "graphic", "icon", "illustration"}:
                detail = f"Mapped image node has only generic computed name {image_name!r}; semantic usefulness needs human review."
            else:
                verdict = "PASS"
            if not detail.startswith("Mapped image node"):
                detail = (
                    f"Mapped image role={_role(image)!r}; computed name={image_name!r}. "
                    "Name accuracy and usefulness still require human review."
                )
        rule = "computed_image_name"
    elif test_case == "TC02":
        field = _target_node(evidence, nodes)
        if field is None:
            detail = "The uniquely mapped email-field node is missing from the Accessibility Tree evidence."
        else:
            evidence_nodes.append(field)
            role = _role(field)
            name = _name(field).strip()
            verdict = "PASS" if role in {"textbox", "text field"} and name == "Email address" else "FAIL"
            detail = f"Mapped field role={role!r}; computed name={name!r}; expected textbox named 'Email address'."
        rule = "computed_textbox_name_matches_visible_label"
    elif test_case == "TC03":
        control = _target_node(evidence, nodes)
        status = _target_node(evidence, nodes, "status")
        if control is None:
            detail = "The uniquely mapped custom-control node is missing from the Accessibility Tree evidence."
        else:
            evidence_nodes.append(control)
            if _role(control) == "button" and _name(control).strip() == "Run test" and not control.get("ignored", False):
                verdict = "PASS"
            else:
                verdict = "FAIL"
            detail = f"Mapped control nodeId={control.get('nodeId')!r}; role={_role(control)!r}; computed name={_name(control)!r}."
        if status is not None:
            evidence_nodes.append(status)
        final_state = evidence.get("final")
        activation_attempted = (
            evidence.get("keyboard_activation_attempted") is True
            or (
                isinstance(final_state, dict)
                and final_state.get("keyboard_activation_attempted") is True
            )
        )
        activation_text = f"{_name(status)} {_descendant_text(status, nodes)}" if status is not None else ""
        activation_succeeded = "Activated 2 times." in activation_text
        tab_sequence = evidence.get("tab_sequence")
        target_backend_id = control.get("backendDOMNodeId") if control is not None else None
        target_focused_by_tab = any(
            node.get("backendDOMNodeId") == target_backend_id
            and _properties(node).get("focused") is True
            for state in (tab_sequence if isinstance(tab_sequence, list) else [])
            for node in (
                state.get("nodes", []) if isinstance(state, dict) else []
            )
        )
        rule = "computed_button_role_and_name"
        sub_checks.append(
            {
                "assertion": "sequential keyboard focusability",
                "criterion": "2.1.1",
                "verdict": (
                    "NOT_TESTABLE"
                    if not isinstance(tab_sequence, list) or not tab_sequence
                    else ("PASS" if target_focused_by_tab else "FAIL")
                ),
                "rule": "sequential_tab_reaches_accessible_control",
                "evidence": (
                    f"Accessibility Tree states captured after Tab={len(tab_sequence) if isinstance(tab_sequence, list) else 0}; "
                    f"mapped target nodeId={(control.get('nodeId') if control else None)!r}; "
                    f"focused in sequence={target_focused_by_tab}."
                ),
            }
        )
        sub_checks.append(
            {
                "assertion": "Enter/Space activation after focus",
                "criterion": "2.1.1",
                "verdict": (
                    "NOT_TESTABLE"
                    if not activation_attempted or status is None
                    else ("PASS" if activation_succeeded else "FAIL")
                ),
                "rule": "accessible_activation_result_after_focus",
                "evidence": (
                    f"Target reached by Tab={target_focused_by_tab}; keyboard activation attempted={activation_attempted}; "
                    f"mapped status role={_role(status)!r}, computed name={_name(status)!r}, "
                    f"descendant text={_descendant_text(status, nodes)!r}."
                    if status is not None
                    else f"Target reached by Tab={target_focused_by_tab}; keyboard activation attempted={activation_attempted}; "
                    "mapped status node is unavailable."
                ),
            }
        )
    elif test_case == "TC04":
        button = _target_node(evidence, nodes)
        if button is not None:
            evidence_nodes.append(button)
            visible_names = " ".join(_child_names(button, nodes)).casefold()
            computed_name = _name(button).casefold()
            if not visible_names:
                verdict = "NOT_TESTABLE"
                detail = f"Computed button name={_name(button)!r}; visible text is not separately exposed in child nodes."
            else:
                verdict = "PASS" if visible_names in computed_name else "FAIL"
                detail = f"Computed name={computed_name!r}; exposed child text={visible_names!r}."
        else:
            detail = "The uniquely mapped Search button node is missing from the Accessibility Tree evidence."
        rule = "computed_name_contains_ax_exposed_label"
    elif test_case == "TC05":
        initial = evidence.get("initial")
        initial_nodes = _nodes(evidence, "initial")
        initial_target = _target_node(initial, initial_nodes) if isinstance(initial, dict) else None
        target = _target_node(evidence, nodes)
        tab_sequence = evidence.get("tab_sequence")
        if initial_target is None or target is None or not isinstance(tab_sequence, list) or not tab_sequence:
            detail = "Mapped initial/final target nodes and sequential-Tab Accessibility Tree states are required."
        else:
            evidence_nodes.append(target)
            backend_node_id = target.get("backendDOMNodeId")
            initial_reasons = initial_target.get("ignoredReasons", [])
            hidden_initially = initial_target.get("ignored", False) and any(
                isinstance(reason, dict) and reason.get("name") == "ariaHiddenSubtree"
                for reason in initial_reasons
            )
            focused_during_tab = []
            for state in tab_sequence:
                state_nodes = state if isinstance(state, list) else (
                    state.get("nodes", []) if isinstance(state, dict) else []
                )
                focused_during_tab.extend(
                    node for node in state_nodes
                    if node.get("backendDOMNodeId") == backend_node_id
                    and _properties(node).get("focusable") is True
                    and _properties(node).get("focused") is True
                )
            if initial_target.get("ignored", False) and not hidden_initially:
                verdict = "NOT_TESTABLE"
            else:
                verdict = "FAIL" if hidden_initially and focused_during_tab else "PASS"
            detail = (
                f"Mapped target backendDOMNodeId={backend_node_id!r}; hidden by aria-hidden initially="
                f"{hidden_initially}; focusable and focused states during sequential Tab="
                f"{len(focused_during_tab)}. This is a fixture-specific "
                "check, not full ACT-rule coverage."
            )
        rule = "fixture_target_ignored_while_sequentially_focused"
    elif test_case == "TC06":
        shadow_button = _target_node(evidence, nodes)
        if shadow_button is not None:
            evidence_nodes.append(shadow_button)
            verdict = (
                "PASS"
                if _role(shadow_button) == "button" and _name(shadow_button).strip() and not shadow_button.get("ignored", False)
                else "FAIL"
            )
            detail = f"Mapped shadow control role={_role(shadow_button)!r}; computed name={_name(shadow_button)!r}."
        else:
            detail = "The uniquely mapped shadow-button node is missing from the Accessibility Tree evidence."
        rule = "shadow_button_computed_name"
    elif test_case == "TC07":
        status = _target_node(evidence, nodes)
        if status is not None:
            evidence_nodes.append(status)
            message_present = "Item saved successfully." in _descendant_text(status, nodes)
            verdict = "PASS" if _role(status) == "status" and message_present else "FAIL"
            detail = f"Mapped status role={_role(status)!r}; updated message is exposed={message_present}."
        else:
            detail = "The uniquely mapped status-message node is missing from the Accessibility Tree evidence."
        rule = "computed_status_role_after_update"
    elif test_case == "TC08":
        verdict = "NOT_TESTABLE"
        rule = "error_description_relationship_not_wcag_verdict"
        field = _target_node(evidence, nodes)
        if field is not None:
            evidence_nodes.append(field)
            detail = (
                f"Mapped field role={_role(field)!r}; computed name={_name(field)!r}. "
                "Tree relationships alone cannot establish whether the error was identified and described in text."
            )
        else:
            detail = (
                "The mapped email field is unavailable, and Accessibility Tree relationships alone cannot "
                "establish whether the error was identified and described in text."
            )
    elif test_case == "TC09":
        settings = _target_node(evidence, nodes)
        disclosure = _target_node(evidence, nodes, "disclosure")
        if settings is not None:
            evidence_nodes.append(settings)
            selected = _properties(settings).get("selected")
            verdict = (
                "NOT_TESTABLE"
                if _role(settings) != "tab" or selected is None
                else ("PASS" if selected is True else "FAIL")
            )
            detail = (
                f"Mapped tab nodeId={settings.get('nodeId')!r}; role={_role(settings)!r}; "
                f"name={_name(settings)!r}; selected={selected!r}."
            )
        else:
            detail = "The uniquely mapped Settings tab is missing from the Accessibility Tree evidence."
        if disclosure is not None:
            evidence_nodes.append(disclosure)
        if disclosure is not None:
            expanded = _properties(disclosure).get("expanded")
            sub_checks.append(
                {
                    "assertion": "expanded state on activated disclosure",
                    "criterion": "4.1.2",
                    "verdict": (
                        "NOT_TESTABLE"
                        if _role(disclosure) != "button" or expanded is None
                        else ("PASS" if expanded is True else "FAIL")
                    ),
                    "rule": "computed_disclosure_expanded_state",
                    "evidence": (
                        f"Mapped disclosure nodeId={disclosure.get('nodeId')!r}; role={_role(disclosure)!r}; "
                        f"name={_name(disclosure)!r}; expanded={expanded!r}."
                    ),
                }
            )
        else:
            sub_checks.append(
                {
                    "assertion": "expanded state on activated disclosure",
                    "criterion": "4.1.2",
                    "verdict": "NOT_TESTABLE",
                    "rule": "computed_disclosure_expanded_state",
                    "evidence": "The mapped disclosure button is missing from the Accessibility Tree evidence.",
                }
            )
        rule = "computed_tab_selected_state"
    elif test_case == "TC10":
        root = next((node for node in nodes if _role(node) == "RootWebArea"), None)
        if root is not None and _name(root):
            evidence_nodes.append(root)
            verdict = "PASS" if "reports" in _name(root).casefold() else "FAIL"
            detail = f"Computed root web area name={_name(root)!r}; expected it to identify Reports."
        else:
            detail = "The Accessibility Tree does not contain a named RootWebArea node."
        rule = "root_web_area_computed_title"
    elif test_case == "TC11":
        main = _target_node(evidence, nodes)
        if main is not None:
            evidence_nodes.append(main)
            properties = _properties(main)
            focused = properties.get("focused", False)
            verdict = (
                "NOT_TESTABLE"
                if "focused" in properties and not isinstance(focused, bool)
                else ("PASS" if _role(main) == "main" and focused else "FAIL")
            )
            detail = (
                f"Mapped main nodeId={main.get('nodeId')!r}; role={_role(main)!r}; "
                f"focused={focused!r} (an absent focus property is false in a complete full-tree snapshot)."
            )
        else:
            detail = "The uniquely mapped main-content node is missing from the Accessibility Tree evidence."
        rule = "focused_main_after_route_change_observation"
    elif test_case == "TC12":
        opened = evidence.get("dialog_open", {})
        closed = evidence.get("dialog_closed", {})
        open_nodes = _nodes(evidence, "dialog_open")
        closed_nodes = _nodes(evidence, "dialog_closed")
        dialog = _target_node(opened, open_nodes, "dialog") if isinstance(opened, dict) else None
        close_button = _target_node(opened, open_nodes, "close") if isinstance(opened, dict) else None
        opener = _target_node(closed, closed_nodes, "opener") if isinstance(closed, dict) else None
        if dialog is not None:
            evidence_nodes.append(dialog)
        if close_button is not None:
            evidence_nodes.append(close_button)
        if opener is not None:
            evidence_nodes.append(opener)
        if dialog is None or close_button is None or opener is None:
            detail = "Mapped dialog, close-button and opener nodes are required in the captured open/closed states."
        else:
            dialog_properties = _properties(dialog)
            close_properties = _properties(close_button)
            opener_properties = _properties(opener)
            modal = dialog_properties.get("modal", False)
            close_focused = close_properties.get("focused", False)
            opener_focused = opener_properties.get("focused", False)
            required_boolean_states = (
                isinstance(modal, bool)
                and isinstance(close_focused, bool)
                and isinstance(opener_focused, bool)
            )
            if not required_boolean_states:
                detail = (
                    f"Mapped dialog nodeId={dialog.get('nodeId')!r}, modal={modal!r}; "
                    f"close focus={close_focused!r}; opener focus={opener_focused!r}. "
                    "At least one required Accessibility Tree property is unavailable."
                )
            else:
                entry_ok = _role(close_button) == "button" and close_focused is True
                return_ok = _role(opener) == "button" and opener_focused is True
                verdict = "PASS" if modal is True and entry_ok and return_ok else "FAIL"
                detail = (
                    f"Mapped dialog nodeId={dialog.get('nodeId')!r}; role={_role(dialog)!r}; modal={modal!r}; "
                    f"close nodeId={close_button.get('nodeId')!r} focused={close_focused!r}; "
                    f"opener nodeId={opener.get('nodeId')!r} focused={opener_focused!r}."
                )
        rule = "dialog_semantics_and_ax_focus_observation"
    elif test_case == "TC13":
        verdict = "NOT_TESTABLE"
        rule = "visual_focus_indicator_not_encoded_in_ax_tree"
        detail = "Accessibility Tree nodes do not encode the rendered visibility of a focus indicator."
    elif test_case == "TC14":
        verdict = "NOT_TESTABLE"
        rule = "contrast_not_encoded_in_ax_tree"
        detail = "Accessibility Tree semantics do not provide the rendered foreground/background contrast needed for this criterion."

    if evidence_nodes:
        node_details = "; ".join(
            f"nodeId={node.get('nodeId')!r}, backendDOMNodeId={node.get('backendDOMNodeId')!r}, "
            f"role={_role(node)!r}, name={_name(node)!r}, properties={_properties(node)!r}"
            for node in evidence_nodes
        )
        detail = f"{detail} Evidence node details: {node_details}."

    elapsed = time.perf_counter() - started
    return build_result(
        test_case=test_case,
        variant=variant,
        engine="AX",
        criterion=case["criterion"],
        criterion_status=case["mapping_status"],
        verdict=verdict,
        rule=rule,
        evidence=detail,
        execution_time=elapsed,
        run_index=run_index,
        sub_checks=sub_checks,
    )
