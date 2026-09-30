from pathlib import Path

from betamac.scenarios.scenario_review import create_prompt
from betamac.scenarios import scenario_review


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
