from flask import current_app

from .helpers import scenario_messages_to_str, scenario_problem_statement_to_str
from .integrations import jev


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


# returns list[(criteria, pass/fail)] or None on fail
# TODO: review if default state should be an error state (return None) OR a failed all criteria state (return list of False strings)
def grade_text_message(
    user_response: str, scenario_id: str
) -> dict[str, bool] | None:

    scenario = current_app.config["SCENARIOS"][scenario_id]
    # NOTE: skips actual grading for testing
    return testing_sentinel_answers("", scenario["criteria"])

    jev_response = fetch_jev_grading(
        user_response,
        scenario["problem_statement"],
        scenario["messages"],
        scenario["criteria"],
    )

    if not jev_response:
        return None

    answers = jev_response.get("answers")

    if not answers:
        return None

    criteria_met = {}
    for i, criterion in enumerate(scenario["criteria"]):
        criteria_met[criterion] = (
            answers[f"q{i}"]["noul"] > current_app.config["JEV_TRUE_THRESHOLD"]
        )

    return criteria_met
