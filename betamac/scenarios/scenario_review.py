import datetime
import json
import logging
import re
from collections.abc import Collection
from pathlib import Path

from flask import current_app

from betamac.helpers import (
    scenario_criteria_to_dotpoint_str,
    scenario_id_to_str,
    scenario_to_str,
)
from betamac.integrations import analysis_model, jev

logger = logging.getLogger(__name__)


def build_jev_state(
    problem_statement: str | None, messages: list[dict[str, str]]
) -> dict:
    d = {
        **current_app.config["SCENARIO_REVIEW"]["state"],
        "messages": messages,
    }
    if problem_statement:
        d["context"] = problem_statement

    return d


def build_jev_questions(to_ask_about_problem_statement: bool = True) -> dict:
    # build questions
    questions = {}
    for k, v in current_app.config["SCENARIO_REVIEW"]["questions"].items():
        if (
            k != "problem_statement_and_messages_agree"
            or to_ask_about_problem_statement
        ):
            questions[k] = v["question"]

    return questions


def is_question_rejected(noul: float, question_details: dict) -> bool:
    # assume scenario_review.json is correctly formed
    if question_details["reject_if"] == "above":
        return noul > question_details["threshold"]
    return noul < question_details["threshold"]


def jev_response_breakdown(
    answers: dict, asked_questions: Collection[str] | None = None
) -> dict[str, dict]:
    # asked_questions: names of the questions sent to Jev (default: all of
    # them). Questions that weren't asked are skipped rather than missing.

    # {"question_name": {"noul", "threshold", "reject_if", "rejected"}}
    question_breakdown = {}
    for question, question_details in current_app.config["SCENARIO_REVIEW"][
        "questions"
    ].items():
        if asked_questions is not None and question not in asked_questions:
            continue
        try:
            answer = answers[question]
        except KeyError as e:
            raise ValueError(
                "Jev did not provide answer to one or more questions!"
            ) from e

        try:
            answer_noul = answer["noul"]
        except KeyError as e:
            raise ValueError(f'Missing noul for question "{question}"') from e

        question_breakdown[question] = {
            "noul": answer_noul,
            "threshold": question_details["threshold"],
            "reject_if": question_details["reject_if"],
            "rejected": is_question_rejected(answer_noul, question_details),
        }

    return question_breakdown


# returns whether scenario meets criteria per Jev review or throw if Jev
# response failed
def jev_review(
    problem_statement: str | None, messages: list[dict[str, str]]
) -> bool:
    record = {
        "problem_statement": problem_statement,
        "messages": messages,
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # only ask whether the context agrees with the messages if there is one
    questions = build_jev_questions(bool(problem_statement))
    jev_response = jev.fetch_answers(
        build_jev_state(problem_statement, messages), questions
    )
    if not jev_response:
        record["outcome"] = "error"
        record["error"] = "Jev API failure"
        logger.error(json.dumps(record, ensure_ascii=False))
        raise ValueError("Jev API failure")

    record["jev_response_id"] = jev_response.get("id")
    if jev_response.get("usage"):
        record["jev_cost"] = jev_response["usage"].get("cost")

    try:
        answers = jev_response["answers"]
    except KeyError as e:
        record["outcome"] = "error"
        record["error"] = "Jev provided no answers"
        logger.error(json.dumps(record, ensure_ascii=False))
        raise ValueError("Jev provided no answers") from e

    try:
        record["review_questions"] = jev_response_breakdown(answers, questions)
    except ValueError as e:
        record["outcome"] = "error"
        record["error"] = str(e)
        logger.error(json.dumps(record, ensure_ascii=False))
        raise

    # if any question is rejected, scenario doesn't pass
    if any(q["rejected"] for q in record["review_questions"].values()):
        record["outcome"] = "rejected"
        logger.info(json.dumps(record, ensure_ascii=False))
        return False

    record["outcome"] = "accepted"
    logger.info(json.dumps(record, ensure_ascii=False))
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


# use Deepseek to formulate new scenario
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

    if response is None:
        raise ValueError("Scene creator model request failed")

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
        raise ValueError("Model response does not follow expected format")

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

    new_scenario = {
        "id": scenario_id,
        "problem_statement": scenario_problem_statement,
        "messages": scenario_messages,
        "criteria": [re.search(r"- (.*)", c)[1] for c in model_message[1:]],
    }

    return new_scenario
