import json


# format: "<id>", dropping number portion
def scenario_id_to_str(scenario_id: str) -> str:
    return f"{scenario_id[:-4]}"


# format: "<scenario problem statement>"
def scenario_problem_statement_to_str(scenario_problem_statement: str) -> str:
    return (
        json.dumps(scenario_problem_statement)
        if scenario_problem_statement
        else "none"
    )


# return scenario messages as single string
def scenario_messages_to_str(scenario_messages: list[dict]) -> str:
    # assume messages are well-formed
    if len(scenario_messages) == 0:
        return ""

    lines = [
        f"{m['sender']}: {json.dumps(m['text'], ensure_ascii=False)}"
        for m in scenario_messages
    ]

    return "\n".join(lines)


# into format: "- <criteria 1>\n- <criteria 2>", etc
def scenario_criteria_to_dotpoint_str(scenario_criteria: list[str]) -> str:
    lines = [f"- {criterion}" for criterion in scenario_criteria]

    return "\n".join(lines)


# returns scenario context + messages as single string like:
# Context: 'problem statement"\ncontact: "hello"\nuser: "hey"'
def scenario_to_str(
    scenario_problem_statement: str, scenario_messages: list[dict]
) -> str:
    lines = [
        "Context: "
        + scenario_problem_statement_to_str(scenario_problem_statement),
        scenario_messages_to_str(scenario_messages),
    ]
    return "\n".join(lines)
