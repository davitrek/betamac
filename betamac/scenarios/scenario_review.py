from pathlib import Path

from flask import current_app
import re

from betamac.helpers import (
    scenario_criteria_to_dotpoint_str,
    scenario_id_to_str,
    scenario_to_str,
)
from betamac.integrations import analysis_model, jev


def build_jev_state(messages: list[list[str, str]]) -> str:
    s = "A text message exchange between two people, 'user' and 'contact' includes the following messages: "
    for m in messages:
        s += f"{m[0]}: {m[1]}\n"

    return s


def build_jev_questions() -> dict:
    # build questions
    questions = {}
    questions["leading_somewhere"] = {
        "type": "noul",
        "instructions": "The messages in this conversation have a purpose and are leading somewhere",
        "criteria": {
            "true": "Message forms a conversation with a purpose",
            "false": "Messages do not have purpose or do not form a conversation",
        },
    }
    questions["is_users_turn"] = {
        "type": "noul",
        "instructions": "It is user's turn to send a message next",
        "criteria": {
            "true": "I expect user to send a message next",
            "false": "I expect contact to send a message next or the conversation has ended",
        },
    }

    return questions


def jev_review(messages: list[list[str, str]]):
    jev_response = jev.fetch_answers(
        build_jev_state(messages), build_jev_questions()
    )
    if not jev_response:
        return None

    answers = jev_response["answers"]
    if not answers:
        return None

    if (
        answers["leading_somewhere"]["noul"]
        > current_app.config["JEV_TRUE_THRESHOLD"]
        and answers["is_users_turn"]["noul"]
        > current_app.config["JEV_TRUE_THRESHOLD"]
    ):
        return True


def create_prompt(
    example_scenarios: list[dict],
    scenario_problem_statement: str,
    scenario_messages: list[dict],
) -> str:
    with open(
        Path(__file__).resolve().parent / "scenario_criteria_creation_prompt"
    ) as f:
        instructions = f.read()
    lines = [instructions]
    for example_scenario in example_scenarios:
        lines += [
            "Example input:",
            scenario_to_str(
                example_scenario["problem_statement"],
                example_scenario["messages"],
            ),
            "",  # line break
            "Example output:",
            "id: " + scenario_id_to_str(example_scenario["id"]),
            scenario_criteria_to_dotpoint_str(example_scenario["criteria"]),
            "",  # line break
        ]
    lines += [
        "Input:",
        scenario_to_str(scenario_problem_statement, scenario_messages),
    ]

    return "\n".join(lines)


def create_new_scenario(
    scenario_problem_statement: str, scenario_messages: list[dict]
) -> dict:
    scenario_examples = [
        current_app.config["SCENARIOS"]["job-loss-001"],
        current_app.config["SCENARIOS"]["pushy-classmate-001"],
        current_app.config["SCENARIOS"]["short-film-001"],
        current_app.config["SCENARIOS"]["party-invite-001"],
        current_app.config["SCENARIOS"]["breakup-vent-001"],
    ]

    response = analysis_model.fetch_answers(
        create_prompt(
            scenario_examples, scenario_problem_statement, scenario_messages
        )
    )

    print(response["choices"][0]["message"]["content"])
    # print(response["usage"]["cost"])

    # assert cost of this was <USD$0.01
    assert response["usage"]["cost"] < 0.01

    # expected format of model_message
    # "id: <scenario id>",
    # "- <criterion>"
    # "- <criterion>"
    # <more criteria if extant>
    model_message = response["choices"][0]["message"]["content"].splitlines()

    # check response follows provided format
    if not model_message[0][:3] == "id:":
        raise ValueError("Response does not follow expected format")

    idx = 3
    # skip space if there is one (there is supposed to be)
    if model_message[0][idx] == " ":
        idx += 1

    scenario_id_name = model_message[0][idx:]
    scenario_id_number = 1
    scenario_id = ""
    # max value storeable in "funny-clown-001" format is 999
    while scenario_id_number < 999:
        scenario_id = f"{scenario_id_name}-{scenario_id_number:03}"
        if scenario_id in current_app.config["SCENARIOS"]:
            scenario_id_number += 1
        else:
            break
    else:
        # don't expect to realistically happen
        assert 0

    new_scenario = {"id": scenario_id}
    new_scenario["problem_statement"] = scenario_problem_statement
    new_scenario["messages"] = scenario_messages
    new_scenario["criteria"] = [
        re.search(r"- (.*)", c)[1] for c in model_message[1:]
    ]

    return new_scenario
