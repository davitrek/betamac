import random

from flask import Blueprint, current_app, render_template, request

from . import marking

bp = Blueprint("drill", __name__)


@bp.route("/", methods=["GET", "POST"])
def drill():
    if request.method == "POST":
        # Posted by static/drill.js; returns only the results fragment.
        submitted = request.form.get("text")
        scenario_id = request.form.get("scenario_id")
        scenario_criteria = current_app.config["SCENARIOS"][scenario_id]["criteria"]

        criteria_met = marking.mark_to_criteria(submitted, scenario_criteria)

        return render_template("grade_results.html", results=criteria_met)

    chosen_scenario = random.choice(
        list(current_app.config["SCENARIOS"].values())
    )

    return render_template(
        "drill.html",
        messages=chosen_scenario["messages"],
        scenario_id=chosen_scenario["id"],
    )
