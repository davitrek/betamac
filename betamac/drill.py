import random

from flask import Blueprint, current_app, render_template, request, session

from . import grading

bp = Blueprint("drill", __name__)


@bp.route("/")
def drill():
    seen_scenarios = set(session.get("seen_scenarios", []))

    new_scenarios = [
        s
        for sid, s in current_app.config["SCENARIOS"].items()
        if sid not in seen_scenarios
    ]

    # if all scenarios seen (no new scenarios), clear seen scenarios so user can
    # start again
    if not new_scenarios:
        session["seen_scenarios"] = []
        new_scenarios = list(current_app.config["SCENARIOS"].values())

    chosen_scenario = random.choice(new_scenarios)

    return render_template(
        "drill.html",
        messages=chosen_scenario["messages"],
        scenario_id=chosen_scenario["id"],
        problem_statement=chosen_scenario["problem_statement"],
    )


@bp.route("/grade", methods=["POST"])
def grade():
    # Posted by static/drill.js as JSON {"scenario_id": ..., "messages": [...]};
    # returns only the results fragment.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return "Invalid request!", 400
    messages = data.get("messages")
    if (
        not isinstance(messages, list)
        or not messages
        or not all(isinstance(m, str) and m.strip() for m in messages)
    ):
        return "Invalid text response!", 400
    scenario_id = data.get("scenario_id")
    if (
        not isinstance(scenario_id, str)
        or scenario_id not in current_app.config["SCENARIOS"]
    ):
        return "Invalid scenario!", 400

    # grading takes one string: one message per line
    submitted_message = "\n".join(messages)

    criteria_met = grading.grade_text_message(submitted_message, scenario_id)

    if criteria_met is None:
        return "Grading failed", 500

    # if user submits *valid* result, add it to cookies so they don't see it again
    session["seen_scenarios"] = [
        *session.get("seen_scenarios", []),
        scenario_id,
    ]
    session.permanent = True

    return render_template("grade_results.html", results=criteria_met)
