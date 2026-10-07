import pytest

from betamac.helpers import (
    scenario_messages_to_str,
    scenario_to_str,
    message_list_form_to_dict_form,
)


@pytest.mark.parametrize(
    "messages, expected_output",
    [
        pytest.param(
            [{"sender": "user", "text": "hello"}], 'user: "hello"', id="happy"
        ),
        pytest.param(
            [{"sender": "user", "text": "😭"}], 'user: "😭"', id="emoji"
        ),
        pytest.param(
            [{"sender": "user", "text": '"'}], 'user: "\\""', id="double_quote"
        ),
        pytest.param(
            [{"sender": "user", "text": "'"}], 'user: "\'"', id="single_quote"
        ),
        pytest.param(
            [{"sender": "user", "text": "\n"}], 'user: "\\n"', id="newline"
        ),
    ],
)
def test_single_message(messages, expected_output):
    output = scenario_messages_to_str(messages)
    assert output == expected_output


def test_empty_messages():
    messages = []
    output = scenario_messages_to_str(messages)
    expected_output = ""

    assert output == expected_output


def test_multiple_messages():
    messages = [
        {"sender": "user", "text": "hello"},
        {"sender": "contact", "text": "world"},
    ]
    output = scenario_messages_to_str(messages)
    expected_output = 'user: "hello"\ncontact: "world"'

    assert output == expected_output


@pytest.mark.parametrize(
    "scenario, expected_output",
    [
        pytest.param(
            {
                "problem_statement": "test problem",
                "messages": [{"sender": "user", "text": "hello"}],
            },
            'Context: "test problem"\nuser: "hello"',
            id="happy",
        ),
        pytest.param(
            {
                "problem_statement": "'",
                "messages": [{"sender": "user", "text": "hello"}],
            },
            'Context: "\'"\nuser: "hello"',
            id="single_quote_unescaped",
        ),
        pytest.param(
            {
                "problem_statement": '"',
                "messages": [{"sender": "user", "text": "hello"}],
            },
            'Context: "\\""\nuser: "hello"',
            id="double_quote_escaped",
        ),
        pytest.param(
            {
                "problem_statement": "\n",
                "messages": [{"sender": "user", "text": "hello"}],
            },
            'Context: "\\n"\nuser: "hello"',
            id="newline_escaped",
        ),
        pytest.param(
            {
                "problem_statement": "",
                "messages": [{"sender": "user", "text": "hello"}],
            },
            'Context: none\nuser: "hello"',
            id="no_context",
        ),
    ],
)
def test_scenario_to_str(scenario, expected_output):
    output = scenario_to_str(
        scenario["problem_statement"], scenario["messages"]
    )
    assert output == expected_output


@pytest.mark.parametrize(
    "messages, expected_output",
    [
        pytest.param(
            [["user", "hello"]],
            [{"sender": "user", "text": "hello"}],
            id="single_message",
        ),
        pytest.param(
            [["user", "hello"], ["contact", "hey"], ["user", "what's up"]],
            [
                {"sender": "user", "text": "hello"},
                {"sender": "contact", "text": "hey"},
                {"sender": "user", "text": "what's up"},
            ],
            id="multiple_messages",
        ),
    ],
)
def test_message_list_form_to_dict_form(messages, expected_output):
    output = message_list_form_to_dict_form(messages)
    assert output == expected_output
