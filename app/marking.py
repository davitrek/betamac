import json

import requests
from flask import current_app

from .config import Config


def build_questions(message: str, criteria: list[str]):
    questions = {}
    for i, criterion in enumerate(criteria):
        questions["q" + str(i)] = {
            "type": "noul",
            "instructions": "Does the user "
            + criterion
            + " in this text message?",
            "criteria": {
                "true": "User does " + criterion,
                "false": "User does not " + criterion,
            },
        }

    return questions


def mark_to_criteria(message: str, criteria: list) -> list[tuple[str, bool]]:
    questions = build_questions(message, criteria)

    # The model answers narrow, typed questions about the state. Your code owns the workflow.
    response = requests.post(
        url="https://openrouter.ai/api/alpha/decisions",
        headers={
            "Authorization": "Bearer " + Config.OPENROUTER_API_KEY,
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": "typesafe/jev-1.13",
                "state": "A text message being sent by the user reads '"
                + message
                + "'",
                "questions": questions,
            }
        ),
    )

    answers = response.json()["answers"]

    criteria_met = [0] * len(criteria)
    for i, (criterion, answer) in enumerate(zip(criteria, answers.values())):
        criteria_met[i] = (
            criterion,
            answer["noul"] > current_app.config["JEV_TRUE_THRESHOLD"],
        )

    return criteria_met
