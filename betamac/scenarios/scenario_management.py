import json
import os
from pathlib import Path

from flask import current_app


def load_scenarios(file_path: Path) -> dict[str, dict]:
    with open(file_path) as f:
        return {
            s["id"]: s
            for s in json.load(f)["scenarios"]
            # ideally would check validity of keys here
            # -> each scenario needs a "criteria", "messages", etc.
            # ---> ensure these exist & spelling of keys is correct
        }


def save_scenario(scenarios_path: Path, new_scenario: dict):
    # append to scenarios.json (loaded by create_app on next startup)
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


def add_new_scenario_to_pool(new_scenario: dict):
    current_app.config["SCENARIOS"] = {
        **current_app.config["SCENARIOS"],
        new_scenario["id"]: new_scenario,
    }
