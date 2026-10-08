import pytest
from flask import current_app

from betamac.scenarios.scenario_management import add_new_scenario_to_pool


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
