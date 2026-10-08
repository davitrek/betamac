import datetime
import json
import logging

from flask import current_app

from .helpers import scenario_messages_to_str, scenario_problem_statement_to_str
from .integrations import jev

logger = logging.getLogger(__name__)


def testing_sentinel_answers(message, criteria):
    criteria_met = {}
    for i, criterion in enumerate(criteria):
        criteria_met[f"test sentinel value {i}"] = True

    return criteria_met


def build_questions(criteria: list[str]) -> dict:
    # build questions
    questions = {}
    for i, criterion in enumerate(criteria):
        questions[f"q{i}"] = {
            "type": "noul",
            "instructions": f"Does the user {criterion} in their final response?",
            "criteria": {
                "true": f"User does {criterion}",
                "false": f"User does not {criterion}",
            },
        }

    return questions


def build_state(
    scenario_problem_statement: str,
    scenario_messages: list[dict],
    user_response: str,
) -> str:
    lines = [
        "A text message exchange between 'user' and 'contact'.",
    ]
    if scenario_problem_statement:
        lines += [
            "The context behind the conversation is: ",
            scenario_problem_statement_to_str(scenario_problem_statement)
            + ' (where "you" refers to the user.)',
        ]

    lines += [
        "Each line is one message, oldest first.",
        scenario_messages_to_str(scenario_messages),
        "The final response from the user is:",
        user_response,
    ]

    return "\n".join(lines)


def fetch_jev_grading(
    user_response: str,
    scenario_problem_statement: str,
    scenario_messages: list[dict],
    criteria: list[str],
):
    return jev.fetch_answers(
        build_state(
            scenario_problem_statement, scenario_messages, user_response
        ),
        build_questions(criteria),
    )


def log_grading_error(record: dict, error: str):
    record["outcome"] = "error"
    record["error"] = error
    logger.error(json.dumps(record, ensure_ascii=False))


# returns {"criterion": True/False, i.e., pass/fail} or None on error
def grade_text_message(
    user_response: str, scenario_id: str
) -> dict[str, bool] | None:

    scenario = current_app.config["SCENARIOS"][scenario_id]
    # NOTE: skips actual grading for testing
    # return testing_sentinel_answers("", scenario["criteria"])

    return jev_grade(user_response, scenario)


# grades user_response with Jev and logs one JSONL record per call
def jev_grade(user_response: str, scenario: dict) -> dict[str, bool] | None:
    record = {
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scenario_id": scenario["id"],
        "user_response": user_response,
    }

    jev_response = fetch_jev_grading(
        user_response,
        scenario["problem_statement"],
        scenario["messages"],
        scenario["criteria"],
    )

    if not jev_response:
        log_grading_error(record, "Jev API failure")
        return None

    record["jev_response_id"] = jev_response.get("id")
    if jev_response.get("usage"):
        record["jev_cost"] = jev_response["usage"].get("cost")

    answers = jev_response.get("answers")

    if not answers:
        log_grading_error(record, "Jev provided no answers")
        return None

    threshold = current_app.config["JEV_GRADING_SUCCESS_THRESHOLD"]

    # {criterion: {"question", "noul", "threshold", "met"}}
    record["criteria"] = {}
    criteria_met = {}
    for i, criterion in enumerate(scenario["criteria"]):
        answer = answers.get(f"q{i}")
        if not answer or "noul" not in answer:
            log_grading_error(record, f'Missing noul for question "q{i}"')
            return None

        met = answer["noul"] > threshold
        record["criteria"][criterion] = {
            "question": f"q{i}",
            "noul": answer["noul"],
            "threshold": threshold,
            "met": met,
        }
        criteria_met[criterion] = met

    record["outcome"] = "graded"
    logger.info(json.dumps(record, ensure_ascii=False))

    return criteria_met
