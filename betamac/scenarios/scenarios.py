import json
import os
from pathlib import Path

from flask import Blueprint, current_app, flash, g, render_template, request

from betamac.helpers import message_list_form_to_dict_form
from betamac.limiter import global_key, limiter, outcome_is

from .scenario_review import create_new_scenario, jev_review

bp = Blueprint("scenarios", __name__)


@bp.route("/new-scenario")
def create_new():
    return render_template(
        "new_scenario.html",
        max_messages=current_app.config["SCENARIO_MAX_MESSAGES"],
    )


def save_scenario(new_scenario: dict):
    # append to scenarios.json (loaded by create_app on next startup)
    scenarios_path = (
        Path(current_app.root_path).parent / "scenarios" / "scenarios.json"
    )
    with open(scenarios_path, encoding="utf-8") as f:
        scenarios_data = json.load(f)
    scenarios_data["scenarios"].append(new_scenario)
    # write to a temp file then swap it in, so a failed write can't
    # leave scenarios.json half-written
    tmp_path = scenarios_path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(scenarios_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, scenarios_path)


@bp.route("/submit-scenario", methods=["POST"])
# Rate limits are only charged by the outcome submit() puts in g.outcome:
# "rejected" by Jev, or "accepted" once Deepseek has written the criteria.
# Invalid input, Jev errors and Deepseek errors charge nothing.
@limiter.limit(
    lambda: current_app.config["SUBMISSION_REJECTED_LIMIT"],
    deduct_when=outcome_is("rejected"),
)
@limiter.limit(
    lambda: current_app.config["SUBMISSION_ACCEPTED_LIMIT"],
    deduct_when=outcome_is("accepted"),
)
@limiter.limit(
    lambda: current_app.config["SUBMISSION_GLOBAL_LIMIT"],
    key_func=global_key,
    deduct_when=outcome_is("accepted"),
)
def submit():
    # Posted by static/new_scenario.js as JSON:
    # {"messages": [["user", "Hello"], ["contact", "Hey"], ...]}
    # The JS reloads the page on success, which shows the flashed message.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    messages = data.get("messages")
    problem_statement = data.get("problem_statement", "")
    if not (
        isinstance(messages, list)
        and messages
        and all(
            isinstance(m, list)
            and len(m) == 2
            and m[0] in current_app.config["POSSIBLE_SENDERS"]
            and isinstance(m[1], str)
            and m[1].strip()
            for m in messages
        )
    ):
        flash("Invalid scenario submission!")
        return "Invalid scenario submission!", 400

    # convert messages to preferred form
    # [{"sender": "user/contact", "text": "<message text"}]
    try:
        messages = message_list_form_to_dict_form(messages)
    except ValueError:
        return "Scenario failed to be submitted", 400

    # check if any message is longer than limit
    for i, m in enumerate(messages):
        if len(m["text"]) > current_app.config["MESSAGE_MAX_CHAR_LEN"]:
            return (
                f"Message {i + 1} exceeds {current_app.config['MESSAGE_MAX_CHAR_LEN']} character limit.",
                400,
            )

    # check if last message is from the user
    #                     user VVV
    if messages[-1]["sender"] == current_app.config["POSSIBLE_SENDERS"][0]:
        return "Sender of last message cannot be user!", 400

    # check if all messages are from the user
    for m in messages:
        #                     user VVV
        if m["sender"] != current_app.config["POSSIBLE_SENDERS"][0]:
            break
    else:
        return "There must be at least one message not from the user!", 400

    # review if submission meets guidelines
    try:
        if not jev_review(problem_statement, messages):
            g.outcome = "rejected"
            flash("Submission rejected: does not meet criteria")
            return "", 204
    except ValueError:
        return "Server error", 500

    # -------- get Deepseek to create new JSON scenario entry -------

    try:
        new_scenario = create_new_scenario(problem_statement, messages)
    except ValueError:
        return "Server error", 500
    g.outcome = "accepted"

    save_scenario(new_scenario)

    flash("Scenario submitted!")
    return "", 204
