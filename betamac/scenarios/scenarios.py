import json
import os
from pathlib import Path

from flask import Blueprint, current_app, flash, render_template, request

from .scenario_review import create_new_scenario, jev_review

bp = Blueprint("scenarios", __name__)


@bp.route("/new-scenario")
def create_new():
    return render_template(
        "new_scenario.html",
        max_messages=current_app.config["SCENARIO_MAX_MESSAGES"],
    )


@bp.route("/submit-scenario", methods=["POST"])
def submit():
    # Posted by static/new_scenario.js as JSON:
    # {"messages": [["user", "Hello"], ["contact", "Hey"], ...]}
    # The JS reloads the page on success, which shows the flashed message.
    data = request.get_json(silent=True)
    messages = data.get("messages") if isinstance(data, dict) else None
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

    # check if any message is longer than limit
    for i, m in enumerate(messages):
        if len(m[1]) > current_app.config["MESSAGE_MAX_CHAR_LEN"]:
            return (
                f"Message {i + 1} exceeds {current_app.config['MESSAGE_MAX_CHAR_LEN']} character limit.",
                400,
            )

    # check if last message is from the user
    #                     user VVV
    if messages[-1][0] == current_app.config["POSSIBLE_SENDERS"][0]:
        return "Sender of last message cannot be user!", 400

    # check if all messages are from the user
    for m in messages:
        #                     user VVV
        if m[0] != current_app.config["POSSIBLE_SENDERS"][0]:
            break
    else:
        return "There must be at least one message not from the user!", 400

    # review if submission meets guidelines
    if not jev_review(messages):
        flash("Submission rejected: does not meet criteria")
        return "", 204

    messages = [{"sender": s, "text": t} for s, t in messages]
    new_scenario = create_new_scenario(problem_statement, messages)

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

    flash("Scenario submitted!")
    return "", 204


@bp.route("/test", methods=["GET"])
def test():
    test_scenario = current_app.config["SCENARIOS"]["friend-in-crisis-001"]
    new_scenario = create_new_scenario(
        test_scenario["problem_statement"], test_scenario["messages"]
    )

    return "", 204
