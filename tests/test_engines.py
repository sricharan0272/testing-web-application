from __future__ import annotations

import pytest

from engines.ax_engine import evaluate as evaluate_ax
from engines.dom_engine import evaluate as evaluate_dom
from engines.results import ALLOWED_VERDICTS, build_result


def dom_snapshot(html: str, **extra):
    return {
        "html": html,
        "shadow_roots": [],
        "interaction_states": {},
        "computed_styles": {},
        **extra,
    }


def ax_node(node_id, role, name="", *, ignored=False, children=None, properties=None, sources=None):
    return {
        "nodeId": str(node_id),
        "backendDOMNodeId": node_id,
        "role": {"value": role},
        "name": {"value": name, "sources": sources or []},
        "ignored": ignored,
        "childIds": children or [],
        "properties": [
            {"name": key, "value": {"value": value}}
            for key, value in (properties or {}).items()
        ],
    }


def ax_evidence(nodes, target_backend_node_ids=None, **states):
    evidence = {"final": {"nodes": nodes}, **states}
    if target_backend_node_ids is not None:
        evidence["target_backend_node_ids"] = target_backend_node_ids
    elif nodes:
        evidence["target_backend_node_ids"] = {"primary": nodes[0]["backendDOMNodeId"]}
    return evidence


@pytest.mark.parametrize(
    ("test_case", "variant", "html", "expected"),
    [
        ("TC01", "defective", '<img data-test-image="informative" src="chart.svg">', "FAIL"),
        ("TC01", "conforming", '<img data-test-image="informative" src="chart.svg" alt="Bar chart with increasing values">', "PASS"),
        ("TC02", "defective", '<label for="missing">Email</label><input id="email">', "FAIL"),
        ("TC02", "conforming", '<label for="email">Email</label><input id="email">', "PASS"),
        ("TC04", "defective", '<button id="search-action" aria-label="Find">Search</button>', "FAIL"),
        ("TC04", "conforming", '<button id="search-action" aria-label="Search">Search</button>', "PASS"),
        ("TC05", "defective", '<div aria-hidden="true"><button id="hidden-action">Hidden</button></div>', "FAIL"),
        ("TC05", "conforming", '<button id="hidden-action">Visible</button>', "PASS"),
        ("TC07", "defective", '<p id="status-message">Saved</p>', "FAIL"),
        ("TC07", "conforming", '<p id="status-message" role="status">Saved</p>', "PASS"),
        ("TC08", "defective", '<input id="account-email"><p id="email-error">Invalid</p>', "NOT_TESTABLE"),
        ("TC09", "conforming", '<button id="tab-settings" aria-selected="true"></button><section id="panel-settings"></section>', "PASS"),
        ("TC09", "defective", '<button id="tab-settings" aria-selected="false"></button><section id="panel-settings" hidden></section>', "FAIL"),
        ("TC10", "conforming", '<title>Reports | Lab</title>', "PASS"),
        ("TC10", "defective", '<title>Dashboard | Lab</title>', "FAIL"),
        ("TC13", "conforming", '<button>Focused</button>', "NOT_TESTABLE"),
        ("TC14", "conforming", '<p>High contrast</p>', "NOT_TESTABLE"),
        ("TC14", "defective", '<p>Low contrast</p>', "NOT_TESTABLE"),
    ],
)
def test_dom_engine_rules(test_case, variant, html, expected):
    extras = {}
    if test_case == "TC07":
        extras["interaction_states"] = {"final": {"active_element": {}}}
    if test_case == "TC14":
        extras["computed_styles"] = {
            "contrast": {
                "color": "rgb(23, 32, 51)" if variant == "conforming" else "rgb(170, 170, 170)",
                "background_color": "rgb(255, 255, 255)",
            }
        }
    if test_case == "TC05":
        extras["interaction_states"] = {"tab_sequence": [{"id": "hidden-action"}]}
    if test_case == "TC07":
        html = html.replace("Saved", "Item saved successfully.")
        if variant == "conforming":
            html = html.replace('role="status"', 'role="status" aria-live="polite"')
    result = evaluate_dom(dom_snapshot(html, **extras), test_case, variant)
    assert result["verdict"] == expected
    assert result["engine"] == "DOM"
    assert result["evidence"]


def test_dom_shadow_root_is_part_of_explicit_dom_evidence():
    snapshot = dom_snapshot(
        "<research-action></research-action>",
        shadow_roots=[{"host": "research-action", "html": '<button id="shadow-action"></button>'}],
    )
    assert evaluate_dom(snapshot, "TC06", "defective")["verdict"] == "FAIL"


def test_dom_focus_and_dialog_rules_use_dom_interaction_evidence():
    route = dom_snapshot(
        "<main id='main-content'></main>",
        interaction_states={"final": {"active_element": {"id": "main-content"}}},
    )
    assert evaluate_dom(route, "TC11", "conforming")["verdict"] == "PASS"
    dialog = dom_snapshot(
        "<dialog></dialog>",
        interaction_states={
            "dialog_open": {"active_element": {"id": "dialog-close"}, "modal": True},
            "dialog_closed": {"active_element": {"id": "dialog-opener"}},
        },
    )
    assert evaluate_dom(dialog, "TC12", "conforming")["verdict"] == "PASS"


def test_custom_control_keeps_semantics_separate_from_keyboard_operability():
    defective = dom_snapshot(
        '<div id="custom-action" data-activated="0">Run test</div>',
        interaction_states={
            "keyboard_activation": {
                "tab_sequence_attempted": True,
                "target_focused_by_tab": False,
                "activation_attempted": False,
            }
        },
    )
    result = evaluate_dom(defective, "TC03", "defective")
    assert result["verdict"] == "FAIL"
    assert [check["assertion"] for check in result["sub_checks"]] == [
        "sequential keyboard focusability",
        "Enter/Space activation after focus",
    ]
    assert [check["verdict"] for check in result["sub_checks"]] == ["FAIL", "NOT_TESTABLE"]

    conforming = dom_snapshot(
        '<button id="custom-action" data-activated="2">Run test</button>',
        interaction_states={
            "keyboard_activation": {
                "tab_sequence_attempted": True,
                "target_focused_by_tab": True,
                "activation_attempted": True,
            }
        },
    )
    result = evaluate_dom(conforming, "TC03", "conforming")
    assert [check["verdict"] for check in result["sub_checks"]] == ["PASS", "PASS"]


def test_ax_custom_control_separates_focusability_from_activation():
    button = ax_node(1, "button", "Run test", properties={"focusable": True})
    status = ax_node(2, "status", "Activated 2 times.")
    evidence = ax_evidence(
        [button, status],
        target_backend_node_ids={"primary": 1, "status": 2},
        tab_sequence=[{"nodes": [ax_node(1, "button", "Run test", properties={"focused": True})]}],
        keyboard_activation_attempted=True,
    )
    result = evaluate_ax(evidence, "TC03", "conforming")
    assert [check["assertion"] for check in result["sub_checks"]] == [
        "sequential keyboard focusability",
        "Enter/Space activation after focus",
    ]
    assert [check["verdict"] for check in result["sub_checks"]] == ["PASS", "PASS"]

    defective = ax_evidence(
        [ax_node(3, "generic", "Run test")],
        target_backend_node_ids={"primary": 3},
        tab_sequence=[{"nodes": [ax_node(4, "button", "Other control", properties={"focused": True})]}],
        keyboard_activation_attempted=False,
    )
    result = evaluate_ax(defective, "TC03", "defective")
    assert [check["verdict"] for check in result["sub_checks"]] == ["FAIL", "NOT_TESTABLE"]


def test_dom_evidence_gaps_do_not_become_passes():
    assert evaluate_dom(dom_snapshot("<main></main>"), "TC01", "conforming")["verdict"] == "NOT_TESTABLE"
    generic_alt = '<img data-test-image="informative" alt="image">'
    assert evaluate_dom(dom_snapshot(generic_alt), "TC01", "conforming")["verdict"] == "NOT_TESTABLE"
    duplicate_images = generic_alt + '<img data-test-image="informative" alt="A meaningful chart description">'
    assert evaluate_dom(dom_snapshot(duplicate_images), "TC01", "conforming")["verdict"] == "NOT_TESTABLE"
    unrelated_label = '<label for="other">Email address</label><input id="other"><input id="email">'
    assert evaluate_dom(dom_snapshot(unrelated_label), "TC02", "conforming")["verdict"] == "FAIL"
    duplicate_fields = '<label for="email">Email address</label><input id="email"><input id="email">'
    assert evaluate_dom(dom_snapshot(duplicate_fields), "TC02", "conforming")["verdict"] == "NOT_TESTABLE"
    assert evaluate_dom(
        dom_snapshot(
            '<div id="custom-action">Run test</div>',
            interaction_states={"keyboard_activation": {"tab_sequence_attempted": True}},
        ),
        "TC03",
        "defective",
    )["sub_checks"][0]["verdict"] == "FAIL"
    duplicate_controls = '<button id="custom-action">Run test</button><button id="custom-action">Run test</button>'
    assert evaluate_dom(dom_snapshot(duplicate_controls), "TC03", "conforming")["verdict"] == "NOT_TESTABLE"
    assert evaluate_dom(
        dom_snapshot('<button id="hidden-action">Action</button>'),
        "TC05",
        "conforming",
    )["verdict"] == "NOT_TESTABLE"


@pytest.mark.parametrize(
    ("test_case", "nodes", "expected"),
    [
        ("TC01", [ax_node(1, "image", "Chart")], "PASS"),
        ("TC01", [ax_node(1, "image", "")], "FAIL"),
        ("TC02", [ax_node(1, "textbox", "Email address")], "PASS"),
        ("TC02", [ax_node(1, "textbox", "Email")], "FAIL"),
        ("TC03", [ax_node(1, "button", "Run test"), ax_node(2, "status", "Activated 2 times.")], "PASS"),
        ("TC03", [ax_node(1, "generic", "Run test")], "FAIL"),
        ("TC04", [ax_node(1, "button", "Search", children=["2"]), ax_node(2, "StaticText", "Search")], "PASS"),
        ("TC04", [ax_node(1, "button", "Find", children=["2"]), ax_node(2, "StaticText", "Search")], "FAIL"),
        ("TC06", [ax_node(1, "button", "")], "FAIL"),
        ("TC06", [ax_node(1, "button", "Open preferences")], "PASS"),
        ("TC07", [ax_node(1, "status", "", children=["2"]), ax_node(2, "StaticText", "Item saved successfully.")], "PASS"),
        ("TC07", [ax_node(1, "StaticText", "Item saved successfully.")], "FAIL"),
        ("TC08", [], "NOT_TESTABLE"),
        ("TC09", [ax_node(1, "tab", "Settings", properties={"selected": True})], "PASS"),
        ("TC09", [ax_node(1, "tab", "Settings", properties={"selected": False})], "FAIL"),
        ("TC10", [ax_node(1, "RootWebArea", "Reports | Lab")], "PASS"),
        ("TC10", [ax_node(1, "RootWebArea", "Dashboard | Lab")], "FAIL"),
        ("TC11", [ax_node(1, "main", "Main", properties={"focused": True})], "PASS"),
        ("TC11", [ax_node(1, "RootWebArea", "Page", properties={"focused": True})], "FAIL"),
        ("TC13", [], "NOT_TESTABLE"),
        ("TC14", [], "NOT_TESTABLE"),
    ],
)
def test_ax_engine_rules(test_case, nodes, expected):
    target_ids = {"primary": nodes[0]["backendDOMNodeId"]} if nodes else {}
    additional_evidence = {}
    if test_case == "TC03" and len(nodes) > 1:
        target_ids["status"] = nodes[1]["backendDOMNodeId"]
        additional_evidence["keyboard_activation_attempted"] = True
    if test_case == "TC09" and len(nodes) > 1:
        target_ids["disclosure"] = nodes[1]["backendDOMNodeId"]
    if test_case == "TC05":
        additional_evidence["tab_sequence"] = [{"nodes": nodes}]
    result = evaluate_ax(
        ax_evidence(nodes, target_backend_node_ids=target_ids, **additional_evidence),
        test_case,
        "defective",
    )
    assert result["verdict"] == expected
    assert result["engine"] == "AX"
    assert result["evidence"]


def test_ax_engine_dialog_uses_only_tree_nodes():
    evidence = ax_evidence(
        [],
        dialog_open={
            "nodes": [
                ax_node(1, "dialog", "Research dialog", properties={"modal": True}),
                ax_node(2, "button", "Close dialog", properties={"focused": True}),
            ],
            "target_backend_node_ids": {"dialog": 1, "close": 2},
        },
        dialog_closed={
            "nodes": [ax_node(3, "button", "Open dialog", properties={"focused": True})],
            "target_backend_node_ids": {"opener": 3},
        },
    )
    assert evaluate_ax(evidence, "TC12", "conforming")["verdict"] == "PASS"


def test_ax_targets_use_backend_node_mapping_not_global_name_search():
    unrelated = ax_node(1, "button", "Search")
    target = ax_node(2, "button", "Find", children=["3"])
    text = ax_node(3, "StaticText", "Search")
    result = evaluate_ax(
        ax_evidence(
            [unrelated, target, text],
            target_backend_node_ids={"primary": 2},
        ),
        "TC04",
        "defective",
    )
    assert result["verdict"] == "FAIL"
    assert "backendDOMNodeId=2" in result["evidence"]


def test_ax_missing_target_mapping_is_not_testable():
    result = evaluate_ax(
        {"final": {"nodes": [ax_node(1, "image", "Chart")]}},
        "TC01",
        "conforming",
    )
    assert result["verdict"] == "NOT_TESTABLE"


def test_ax_generic_image_name_is_not_reported_as_pass():
    image = ax_node(1, "image", "image")
    result = evaluate_ax(
        ax_evidence([image], target_backend_node_ids={"primary": 1}),
        "TC01",
        "conforming",
    )
    assert result["verdict"] == "NOT_TESTABLE"


def test_ax_tc05_compares_hidden_initial_state_with_sequential_focus_state():
    hidden = ax_node(1, "none", "", ignored=True)
    hidden["ignoredReasons"] = [{"name": "ariaHiddenSubtree"}]
    focused = ax_node(1, "button", "Reveal details", properties={"focusable": True, "focused": True})
    evidence = {
        "initial": {"nodes": [hidden], "target_backend_node_ids": {"primary": 1}},
        "final": {"nodes": [focused], "target_backend_node_ids": {"primary": 1}},
        "tab_sequence": [{"nodes": [focused]}],
    }
    assert evaluate_ax(evidence, "TC05", "defective")["verdict"] == "FAIL"

    exposed = ax_node(1, "button", "Reveal details", properties={"focusable": True})
    conforming_evidence = {
        "initial": {"nodes": [exposed], "target_backend_node_ids": {"primary": 1}},
        "final": {"nodes": [focused], "target_backend_node_ids": {"primary": 1}},
        "tab_sequence": [{"nodes": [focused]}],
    }
    assert evaluate_ax(conforming_evidence, "TC05", "conforming")["verdict"] == "PASS"


def test_ax_tc05_missing_tab_sequence_is_not_testable():
    target = ax_node(1, "button", "Reveal details")
    evidence = {
        "initial": {"nodes": [target], "target_backend_node_ids": {"primary": 1}},
        "final": {"nodes": [target], "target_backend_node_ids": {"primary": 1}},
    }
    assert evaluate_ax(evidence, "TC05", "conforming")["verdict"] == "NOT_TESTABLE"


def test_ax_tc03_keyboard_result_is_a_separate_assertion():
    nodes = [
        ax_node(1, "button", "Run test"),
        ax_node(2, "status", "", children=["3"]),
        ax_node(3, "StaticText", "Activated 2 times."),
    ]
    evidence = ax_evidence(
        nodes,
        target_backend_node_ids={"primary": 1, "status": 2},
        tab_sequence=[{"nodes": [ax_node(1, "button", "Run test", properties={"focused": True})]}],
        keyboard_activation_attempted=True,
    )
    result = evaluate_ax(evidence, "TC03", "conforming")
    assert result["verdict"] == "PASS"
    assert [check["verdict"] for check in result["sub_checks"]] == ["PASS", "PASS"]


def test_form_error_association_is_not_mislabeled_as_wcag_pass_or_fail():
    dom = evaluate_dom(dom_snapshot('<input><p>Error text</p>'), "TC08", "defective")
    ax = evaluate_ax(ax_evidence([ax_node(1, "textbox", "Email")]), "TC08", "defective")
    assert dom["verdict"] == ax["verdict"] == "NOT_TESTABLE"


def test_common_result_schema_rejects_unknown_verdict():
    assert ALLOWED_VERDICTS == {"PASS", "FAIL", "INAPPLICABLE", "NOT_TESTABLE"}
    with pytest.raises(ValueError):
        build_result(
            test_case="TC01",
            variant="defective",
            engine="DOM",
            criterion="1.1.1",
            verdict="UNKNOWN",
            rule="test",
            evidence="test",
            execution_time=0,
        )
