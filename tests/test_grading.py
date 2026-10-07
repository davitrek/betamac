import json
import logging

import pytest

from betamac import grading
from betamac.integrations import jev

SCENARIO = {
    "id": "test-001",
    "problem_statement": "",
    "messages": [{"sender": "contact", "text": "just got fired"}],
    "criteria": ["express sympathy", "offer to help"],
}


@pytest.mark.parametrize(
    "q0, q1, expected_output",
    [
        pytest.param(
            0.9,
            0.9,
            {"express sympathy": True, "offer to help": True},
            id="all_met",
        ),
        pytest.param(
            0.9,
            0.2,
            {"express sympathy": True, "offer to help": False},
            id="one_met",
        ),
    ],
)
def test_jev_grade(app, monkeypatch, caplog, q0, q1, expected_output):
    caplog.set_level(logging.INFO)
    monkeypatch.setitem(app.config, "JEV_TRUE_THRESHOLD", 0.8)

    monkeypatch.setattr(
        jev,
        "fetch_answers",
        lambda state, questions: {
            "answers": {
                "q0": {"type": "noul", "noul": q0},
                "q1": {"type": "noul", "noul": q1},
            },
            "id": "test-id",
            "usage": {"cost": 0.001},
        },
    )

    output = grading.jev_grade("so sorry, can I help?", SCENARIO)

    assert output == expected_output
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.INFO
    log_msg = json.loads(caplog.records[0].message)
    assert log_msg["outcome"] == "graded"
    assert log_msg["scenario_id"] == "test-001"
    assert log_msg["user_response"] == "so sorry, can I help?"
    assert log_msg["jev_response_id"] == "test-id"
    assert log_msg["criteria"]["offer to help"] == {
        "question": "q1",
        "noul": q1,
        "threshold": 0.8,
        "met": expected_output["offer to help"],
    }


@pytest.mark.parametrize(
    "jev_response, expected_error",
    [
        pytest.param(None, "Jev API failure", id="request_failed"),
        pytest.param({"id": "x"}, "Jev provided no answers", id="no_answers"),
        pytest.param(
            {"answers": {"q0": {"noul": 0.9}}},
            'Missing noul for question "q1"',
            id="missing_answer",
        ),
        pytest.param(
            {"answers": {"q0": {"noul": 0.9}, "q1": {}}},
            'Missing noul for question "q1"',
            id="missing_noul",
        ),
    ],
)
def test_jev_grade_errors(
    app, monkeypatch, caplog, jev_response, expected_error
):
    monkeypatch.setattr(
        jev, "fetch_answers", lambda state, questions: jev_response
    )

    assert grading.jev_grade("hi", SCENARIO) is None

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.ERROR
    log_msg = json.loads(caplog.records[0].message)
    assert log_msg["outcome"] == "error"
    assert log_msg["error"] == expected_error
