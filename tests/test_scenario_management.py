import pytest
from flask import current_app

from betamac.scenarios.scenario_management import (
    add_new_scenario_to_pool,
    is_scenario_valid,
    is_scenarios_valid,
)


@pytest.fixture
def scenario_pool(app, monkeypatch):
    monkeypatch.setitem(
        app.config,
        "SCENARIOS",
        {
            "job-loss-001": {
                "id": "job-loss-001",
                "problem_statement": "",
                "messages": [
                    {"sender": "contact", "text": "hello"},
                ],
                "criteria": [
                    "express sympathy",
                ],
                "criteria_meta": {"source": "user", "scenario_version": 1},
            },
        },
    )


def test_add_new_scenario_to_pool(scenario_pool):
    new_scenario = {
        "id": "new-scenario-001",
        "problem_statement": "",
        "messages": [
            {"sender": "contact", "text": "goodbye"},
        ],
        "criteria": [
            "ask how the contact is feeling",
        ],
        "criteria_meta": {"source": "user", "scenario_version": 1},
    }

    existing_scenario = current_app.config["SCENARIOS"]["job-loss-001"]

    add_new_scenario_to_pool(new_scenario)

    assert "job-loss-001" in current_app.config["SCENARIOS"]
    assert current_app.config["SCENARIOS"]["job-loss-001"] is existing_scenario
    assert len(current_app.config["SCENARIOS"]) == 2
    assert "new-scenario-001" in current_app.config["SCENARIOS"]
    assert "criteria" in current_app.config["SCENARIOS"]["new-scenario-001"]
    assert current_app.config["SCENARIOS"]["new-scenario-001"] is new_scenario


@pytest.mark.parametrize(
    "scenario, valid_senders",
    [
        pytest.param(
            {
                "id": "test-id-001",
                "problem_statement": "",
                "messages": [{"sender": "contact", "text": "hey"}],
                "criteria": ["express sympathy"],
            },
            ("user", "contact"),
            id="valid_scenario",
        ),
    ],
)
def test_is_scenario_valid_accepts_valid_scenario(scenario, valid_senders):
    output = is_scenario_valid(scenario, valid_senders)

    assert output == True


@pytest.mark.parametrize(
    "scenario, valid_senders",
    [
        pytest.param(
            {
                "id": "test-id-001",
                "problem_statement": "",
                "criteria": ["express sympathy"],
            },
            ("user", "contact"),
            id="missing_messages",
        ),
        pytest.param(
            {
                "id": "test-id-001",
                "problem_statement": "",
                "messages": [{"sender": "contact", "text": "hey"}],
                "critera": ["express sympathy"],
            },
            ("user", "contact"),
            id="key_misspelling",
        ),
        pytest.param(
            {
                "id": "test-id-001",
                "problem_statement": "",
                "messages": [{"sender": "test", "text": "hey"}],
                "criteria": ["express sympathy"],
            },
            ("user", "contact"),
            id="invalid_message_sender",
        ),
        pytest.param(
            {
                "id": "",
                "problem_statement": "",
                "messages": [{"sender": "contact", "text": "hey"}],
                "criteria": ["express sympathy"],
            },
            ("user", "contact"),
            id="missing_id",
        ),
        pytest.param(
            {
                "id": "test-id-001",
                "problem_statement": "",
                "messages": [],
                "criteria": ["express sympathy"],
            },
            ("user", "contact"),
            id="no_messages",
        ),
        pytest.param(
            {
                "id": "test-id-001",
                "problem_statement": "",
                "messages": [{"sender": "contact", "text": "hey"}],
                "criteria": [],
            },
            ("user", "contact"),
            id="no_criteria",
        ),
    ],
)
def test_is_scenario_valid_rejects_invalid_scenario(scenario, valid_senders):
    output = is_scenario_valid(scenario, valid_senders)

    assert output == False


def test_is_scenarios_valid_accepts_valid_scenarios():
    scenarios = {
        "job-loss-001": {
            "id": "job-loss-001",
            "problem_statement": "",
            "messages": [{"sender": "contact", "text": "hello"}],
            "criteria": ["express sympathy"],
        },
        "job-gain-001": {
            "id": "job-gain-001",
            "problem_statement": "",
            "messages": [{"sender": "contact", "text": "bye"}],
            "criteria": ["say hello"],
        },
    }

    valid_senders = ("user", "contact")

    output = is_scenarios_valid(scenarios, valid_senders)

    assert output == True


def test_is_scenarios_valid_rejects_invalid_scenarios():
    scenarios = {
        "job-loss-001": {
            "id": "job-loss-001",
            "problem_statement": "",
            "messages": [{"sender": "contact", "text": "hello"}],
            "criteria": ["express sympathy"],
        },
        "job-gain-001": {
            "id": "job-gain-001",
            "problem_statement": "",
            "messages": [],
            "criteria": ["say hello"],
        },
    }

    valid_senders = ("user", "contact")

    output = is_scenarios_valid(scenarios, valid_senders)

    assert output == False
