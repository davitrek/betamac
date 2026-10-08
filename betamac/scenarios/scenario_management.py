import json
import os
from pathlib import Path

from flask import current_app


def load_scenarios(file_path: Path) -> dict[str, dict]:
    with open(file_path) as f:
        return {s["id"]: s for s in json.load(f)["scenarios"]}


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


# checks if a scenario has valid keys and values
def is_scenario_valid(scenario: dict, valid_senders: list) -> bool:
    # scenario has id
    if not scenario.get("id"):
        return False

    # missing problem_statement key
    # -> note, value can validly be ""
    if not "problem_statement" in scenario:
        return False

    if not scenario.get("messages"):
        return False

    # each scenario["messages"] has "sender" and "text"
    if not all(
        "sender" in message and "text" in message
        for message in scenario["messages"]
    ):
        return False

    # each sender is in valid_senders
    if not all(
        message["sender"] in valid_senders for message in scenario["messages"]
    ):
        return False

    # criteria list exists and is not empty
    if not scenario.get("criteria"):  # noqa: SIM103
        return False

    return True


def is_scenarios_valid(scenarios: list[dict], valid_senders: list):
    return all(
        is_scenario_valid(scenario, valid_senders)
        for scenario in scenarios.values()
    )
