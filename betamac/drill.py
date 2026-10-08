import random

from flask import Blueprint, current_app, render_template, request, session

from . import grading
from .limiter import limiter

bp = Blueprint("drill", __name__)


@bp.route("/")
def drill():
    seen_scenarios = set(session.get("seen_scenarios", []))

    new_scenarios = [
        s
        for sid, s in current_app.config["SCENARIOS"].items()
        if sid not in seen_scenarios
    ]

    to_notify_all_scenarios_seen = False
    # if all scenarios alr seen, notify user and choose random scenario to show
    if not new_scenarios:
        chosen_scenario = random.choice(
            list(current_app.config["SCENARIOS"].values())
        )
        # do not show message if it's alr been seen
        if not session.get("all_seen_notified", False):
            to_notify_all_scenarios_seen = True
            session["all_seen_notified"] = True
    else:
        chosen_scenario = random.choice(new_scenarios)
        # re-enable notification once all new scenarios are seen
        # -> will happen if user comes back after new scenarios are added
        session["all_seen_notified"] = False

    return render_template(
        "drill.html",
        messages=chosen_scenario["messages"],
        scenario_id=chosen_scenario["id"],
        problem_statement=chosen_scenario["problem_statement"],
        to_notify_all_scenarios_seen=to_notify_all_scenarios_seen,
    )


@bp.route("/grade", methods=["POST"])
# only successful gradings count; bad input and grading failures don't
@limiter.limit(
    lambda: current_app.config["GRADING_LIMIT"],
    deduct_when=lambda response: response.status_code == 200,
)
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

    # {"criterion": True/False, i.e., pass/fail} or None on error
    criteria_met = grading.grade_text_message(submitted_message, scenario_id)
    if criteria_met is None:
        return "Grading failed", 500

    # if user submits correct solution, add it to cookies so they don't see it again
    if all(criteria_met.values()):
        session["seen_scenarios"] = [
            *session.get("seen_scenarios", []),
            scenario_id,
        ]
        session.permanent = True

    return render_template("grade_results.html", results=criteria_met)
