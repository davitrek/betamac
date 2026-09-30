# CLAUDE.md

This file gives Claude Code guidance for working in this repository.

## What this is

A small Flask app for practising social text-message replies. The user sees a
phone-style chat from a scenario, types a reply, and an LLM grades the reply
against the scenario's criteria (pass/fail per criterion).

## Running

```sh
source .venv/bin/activate
pip install -r requirements.txt   # flask, requests, python-dotenv
flask run                         # from the repo root; .flaskenv sets FLASK_APP=betamac, FLASK_DEBUG=1
```

- `.env` (gitignored) should define `OPENROUTER_API_KEY` and `SECRET_KEY`. `config.py` reads both with `environ.get`, so a missing value is `None` rather than an error. `create_app()` only prints "Missing API key". `SECRET_KEY` is required because `drill.py` uses the Flask `session`.
- VS Code: the "Python Debugger: Flask" launch config in `.vscode/launch.json` does the same thing under debugpy.
- There are no tests, linter, or build step.

## Layout

- `betamac/__init__.py`: `create_app()` factory, which `flask run` finds through `FLASK_APP=betamac`. Loads `scenarios/scenarios.json` into `app.config["SCENARIOS"]` (a dict keyed by scenario `id`) and registers the `drill` and `scenarios` blueprints.
- `betamac/app.py`: empty leftover from the old `app/` layout.
- `betamac/config.py`: `Config` holds the API key, `SECRET_KEY`, `JEV_API_URL` / `JEV_MODEL` (OpenRouter's alpha Decisions API, model `typesafe/jev-1.13`), `JEV_TRUE_THRESHOLD` (0.8, the probability cutoff for counting a criterion as met), `REQUEST_DELAY_S` and `REQUEST_TIMEOUT_S`.
- `betamac/drill.py`: blueprint `drill`.
  - `GET /` (endpoint `drill.drill`) picks a random scenario the user hasn't completed yet. It tracks completed ids in `session["seen_scenarios"]` and resets the list once every scenario has been seen. `drill.html` shows the phone and, 2rem to its right, a `.side` column as tall as the phone. The two are centred together as a pair. At its top is a "Context" box showing `problem_statement`, which is omitted when that's `""`. Below it is `.results`, and under that the Submit button (`.submit-reply`), which sits where Next scenario later appears.
  - `POST /grade` (endpoint `drill.grade`) takes JSON `{"scenario_id": ..., "messages": [text, ...]}`, joins the messages with newlines and grades them with `grading.grade_text_message`, adds the scenario to `seen_scenarios`, and returns only the `grade_results.html` fragment. It returns 400 for bad input (including an empty list or a blank message) and 500 if grading returns `None`.
- `betamac/grading.py`: turns each criterion into a `noul` (yes/no probability) question named `q0`, `q1`, …, POSTs them to the Decisions API and returns `dict[criterion, bool]`. Answers are looked up by key (`q{i}`).
- `betamac/integrations/request_manager.py`: `RequestManager` (module-level singleton `jev_request_manager`) spaces requests by `REQUEST_DELAY_S`, applies `retry-after` delays after a 429, and raises `RequestWaitTooLongError` when the wait would be longer than `REQUEST_TIMEOUT_S`.
- `betamac/scenarios.py`: blueprint `scenarios`.
  - `GET /new-scenario` (endpoint `scenarios.create_new`) renders `new_scenario.html`.
  - `POST /submit-scenario` (endpoint `scenarios.submit`) takes JSON `{"messages": [[sender, text], ...]}`, validates it (`sender` must be `user` or `contact`, and `text` must not be blank) and `flash()`es the outcome, returning 204 on success and 400 if invalid. It doesn't save anything yet.
- `betamac/templates/`: Jinja templates. `layout.html` is the base: a `<nav class="navbar">` (brand link to `/` and a "Submit scenario" pill linking to `/new-scenario`), and the blocks `title`, `flashes` and `main`. By default `flashes` shows flashed messages above `main`. `new_scenario.html` empties it and shows them in bold under its buttons instead. `drill.html`, `grade_results.html` and `new_scenario.html` extend or fill into it.
- `betamac/static/drill.js`: the compose form's send button (or Enter) only adds a sent bubble and appends the text to `sentMessages`. Nothing is posted yet, and whitespace-only messages are skipped. Submit (disabled until one message has been sent) hides itself, disables the form, POSTs the JSON to `data-url` with `data-scenario-id`, adds `.graded` to `.drill` (the `.results` column under the context box fades in) and puts the fragment into `.results-body`. It then shows the `.next-scenario` button, which reloads `/`. Shift+Enter adds a newline.
- `betamac/static/new_scenario.js`: builds message rows (sender `<select>`, text `<input>` and an X remove button) from the `<template id="message-row">` element. The + button adds a row, and the X on the last remaining row is disabled. Submit POSTs JSON `{"messages": [[sender, text], ...]}` to the form's `action` (`scenarios.submit`), and reloads the page on success so the flashed message shows. On failure the rows are kept.
- `betamac/static/style.css`: plain CSS, with no framework loaded. It covers the phone frame, the chat bubbles (`.message.sent` / `.message.received`), the navbar, and a shared `.pill` button class. `.next-scenario` and `.submit-reply` are JavaScript hooks, and `.pill` does the styling (`.pill:disabled` is dimmed). Drill layout: `.context` fits its text up to a third of the phone's height (75vh / 3), and its bubble scrolls beyond that. `.results` sits 1.5rem below it and fills the rest of the column. Inside it, `.results-body` grows and scrolls, and the Next scenario button is pinned to the bottom, level with the phone's bottom edge.

## Conventions and gotchas

- **`betamac/` is a package.** Modules import each other relatively (`from .config import Config`, `from . import grading`). Run things from the repo root as a module, never by file path.
- The blueprints are imported inside `create_app()`, after config is set up. Keep them there.
- **Grading is currently stubbed.** `grade_text_message` returns `testing_sentinel_answers(...)` straight away, so the real API code below it doesn't run. Remove that early return to grade for real.
- Rough edges in `fetch_jev_grading`:
  - `int(response.headers.get("retry-after"))` raises `TypeError` if the header is missing, so the exponential backoff fallback never runs.
- The user's message is inserted straight into the model's `state` string, with no escaping.
- In `style.css`, don't give `.pill` a `display` value. It would override the `hidden` attribute on the Submit and Next scenario buttons.
- `__pycache__` is gitignored. Stale `.pyc` files from deleted modules may still be on disk, but they're harmless.

## Scenarios (`scenarios/scenarios.json`)

```json
{ "scenarios": [ {
  "id": "unique-id-001",
  "problem_statement": "Short context/aim for the user, or \"\" if the chat speaks for itself",
  "messages": [ { "sender": "contact" | "user", "text": "..." } ],
  "criteria": [ "offer to help", "..." ],
  "criteria_meta": { "source": "user", "scenario_version": 1 }
} ] }
```

- `sender == "user"` renders as the player's (sent) bubble, and anything else renders as received.
- Criteria are short verb phrases. They get spliced into prompts as "Does the user <criterion> in their final response?" and "User does <criterion>", so write them to read naturally in that form.
- Scenarios are loaded once at startup, and keys aren't validated. Restart the server (or rely on debug reload) after editing them.
