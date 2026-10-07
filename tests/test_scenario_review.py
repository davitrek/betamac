import json
import logging
from pathlib import Path

import pytest

from betamac.integrations import analysis_model, jev
from betamac.scenarios import scenario_review
from betamac.scenarios.scenario_review import (
    create_prompt,
    jev_response_breakdown,
)


@pytest.fixture
def review_config(app, monkeypatch):
    monkeypatch.setitem(
        app.config,
        "SCENARIO_REVIEW",
        {
            "state": {"description": "test"},
            "questions": {
                "coherent": {
                    "reject_if": "below",
                    "threshold": 0.7,
                    "question": {},
                },
                "hate_or_harassment": {
                    "reject_if": "above",
                    "threshold": 0.3,
                    "question": {},
                },
            },
        },
    )


@pytest.mark.parametrize(
    "answers, expected_output",
    [
        pytest.param(
            {"coherent": {"noul": 0.6}, "hate_or_harassment": {"noul": 0.9}},
            {
                "coherent": {
                    "noul": 0.6,
                    "threshold": 0.7,
                    "reject_if": "below",
                    "rejected": True,
                },
                "hate_or_harassment": {
                    "noul": 0.9,
                    "threshold": 0.3,
                    "reject_if": "above",
                    "rejected": True,
                },
            },
            id="hateful_and_incoherent",
        )
    ],
)
def test_jev_response_breakdown(review_config, answers, expected_output):
    output = jev_response_breakdown(answers)
    assert output == expected_output


def test_create_prompt():
    example_scenarios = [
        {
            "id": "job-loss-001",
            "problem_statement": "",
            "messages": [
                {"sender": "contact", "text": "hey"},
                {"sender": "contact", "text": "just got fired 😭"},
                {
                    "sender": "contact",
                    "text": "u free this weekend? could rly use a hang",
                },
            ],
            "criteria": [
                "express sympathy",
                "ask how the contact is feeling",
                "agree to hang out",
            ],
            "criteria_meta": {"source": "user", "scenario_version": 1},
        },
    ]
    scenario = {
        "id": "short-film-001",
        "problem_statement": "",
        "messages": [
            {"sender": "contact", "text": "yo bro"},
            {
                "sender": "contact",
                "text": "check out this short film i made 🎬",
            },
            {"sender": "contact", "text": "📎 short_film_FINAL_v3.mp4"},
            {
                "sender": "contact",
                "text": "tryna actually get my film career going this year",
            },
        ],
        "criteria": [
            "encourage the contact's filmmaking ambitions",
            "show interest in watching the film",
            "ask a question about the film",
        ],
    }
    output = create_prompt(
        example_scenarios, scenario["problem_statement"], scenario["messages"]
    )
    prompt_path = (
        Path(scenario_review.__file__).resolve().parent
        / "scenario_criteria_creation_prompt"
    )

    with open(prompt_path) as f:
        instructions = f.read() + "\n"
    expected_output = (
        "Example input:\n"
        "Context: none\n"
        'contact: "hey"\n'
        'contact: "just got fired 😭"\n'
        'contact: "u free this weekend? could rly use a hang"\n'
        "\n"
        "Example output:\n"
        "id: job-loss\n"
        "- express sympathy\n"
        "- ask how the contact is feeling\n"
        "- agree to hang out\n"
        "\n"
        "Input:\n"
        "Context: none\n"
        'contact: "yo bro"\n'
        'contact: "check out this short film i made 🎬"\n'
        'contact: "📎 short_film_FINAL_v3.mp4"\n'
        'contact: "tryna actually get my film career going this year"'
    )
    assert output == instructions + expected_output


@pytest.mark.parametrize(
    "coherent, hate, expected_output, expected_outcome",
    [
        pytest.param(0.9, 0.1, True, "accepted", id="clean"),
        pytest.param(0.5, 0.1, False, "rejected", id="incoherent"),
        pytest.param(0.9, 0.6, False, "rejected", id="hateful"),
        pytest.param(0.5, 0.6, False, "rejected", id="incoherent_and_hateful"),
    ],
)
def test_jev_review(
    review_config,
    monkeypatch,
    caplog,
    coherent,
    hate,
    expected_output,
    expected_outcome,
):
    caplog.set_level(logging.INFO)
    calls = []

    def fake_fetch_answers(state, questions):
        calls.append((state, questions))
        return {
            "answers": {
                "coherent": {"type": "noul", "noul": coherent},
                "hate_or_harassment": {"type": "noul", "noul": hate},
            },
            "id": "test-id",
            "usage": {"cost": 0.001},
        }

    monkeypatch.setattr(jev, "fetch_answers", fake_fetch_answers)

    messages = [{"sender": "contact", "text": "hi"}]
    output = scenario_review.jev_review("", messages)

    assert output is expected_output
    assert len(calls) == 1
    state, questions = calls[0]
    assert state["messages"] == messages
    assert "context" not in state
    assert set(questions) == {"coherent", "hate_or_harassment"}
    assert len(caplog.records) == 1
    log_msg = json.loads(caplog.records[0].message)
    assert log_msg["outcome"] == expected_outcome
    assert log_msg["review_questions"]["coherent"]["noul"] == coherent


def test_jev_review_missing_jev_answer(
    review_config,
    monkeypatch,
    caplog,
):
    caplog.set_level(logging.INFO)

    def fake_fetch_answers(state, questions):
        return {
            "answers": {
                "coherent": {"type": "noul", "noul": 0.7},
                # missing:
                # "hate_or_harassment": {"type": "noul", "noul": hate},
            },
            "id": "test-id",
            "usage": {"cost": 0.001},
        }

    monkeypatch.setattr(jev, "fetch_answers", fake_fetch_answers)

    messages = [{"sender": "contact", "text": "hi"}]
    with pytest.raises(ValueError):
        scenario_review.jev_review("", messages)

    assert len(caplog.records) == 1
    log_msg = json.loads(caplog.records[0].message)
    assert log_msg["outcome"] == "error"


def test_jev_review_sends_context(review_config, monkeypatch):
    calls = []

    def fake_fetch_answers(state, questions):
        calls.append(state)
        return {
            "answers": {
                "coherent": {"type": "noul", "noul": 0.9},
                "hate_or_harassment": {"type": "noul", "noul": 0.1},
            }
        }

    monkeypatch.setattr(jev, "fetch_answers", fake_fetch_answers)

    scenario_review.jev_review(
        "your friend is upset", [{"sender": "contact", "text": "hi"}]
    )

    assert calls[0]["context"] == "your friend is upset"


@pytest.mark.parametrize(
    "jev_response",
    [
        pytest.param(None, id="request_failed"),
        pytest.param({"id": "x"}, id="no_answers"),
        pytest.param({"answers": {}}, id="missing_answers"),
        pytest.param({"answers": {"coherent": {}}}, id="missing_noul"),
    ],
)
def test_jev_review_no_answers(review_config, monkeypatch, jev_response):
    monkeypatch.setattr(
        jev, "fetch_answers", lambda state, questions: jev_response
    )

    with pytest.raises(ValueError):
        scenario_review.jev_review("", [{"sender": "contact", "text": "hi"}])


def test_create_new_scenario(app, monkeypatch):
    def fake_fetch_answers(prompt):
        return {
            "choices": [
                {
                    "message": {
                        "content": "id: job-loss\n"
                        "- express sympathy\n"
                        "- offer to help"
                    }
                }
            ],
            "usage": {"cost": 0.001},
        }

    monkeypatch.setattr(analysis_model, "fetch_answers", fake_fetch_answers)

    messages = [{"sender": "contact", "text": "just got fired"}]
    output = scenario_review.create_new_scenario("", messages)

    # job-loss-001 already exists in scenarios.json
    assert output == {
        "id": "job-loss-002",
        "problem_statement": "",
        "messages": messages,
        "criteria": ["express sympathy", "offer to help"],
    }


def test_create_new_scenario_bad_format(app, monkeypatch):
    monkeypatch.setattr(
        analysis_model,
        "fetch_answers",
        lambda prompt: {
            "choices": [{"message": {"content": "- express sympathy"}}],
            "usage": {"cost": 0.001},
        },
    )

    with pytest.raises(ValueError):
        scenario_review.create_new_scenario(
            "", [{"sender": "contact", "text": "just got fired"}]
        )
