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
flask run                         # from the repo root; .flaskenv sets FLASK_APP=app.app, FLASK_DEBUG=1
```

- `.env` (gitignored) must define `OPENROUTER_API_KEY`. `config.py` reads it at import time and raises `KeyError` if it's missing.
- VS Code: the "Python Debugger: Flask" launch config in `.vscode/launch.json` does the same thing under debugpy.
- `python -m app.decisions_demo` is a standalone example of calling the Decisions API. It is not part of the app.
- There are no tests, linter, or build step.

## Layout

- `app/app.py`: `create_app()` factory. Loads `scenarios/scenarios.json` into `app.config["SCENARIOS"]` (a dict keyed by scenario `id`) and registers the `drill` blueprint. A module-level `app` is created for `flask run`.
- `app/config.py`: `Config` holds `OPENROUTER_API_KEY` and `JEV_TRUE_THRESHOLD` (0.8), the probability cutoff for counting a criterion as met.
- `app/drill.py`: blueprint `drill`.
  - `GET /` picks a random scenario and renders `drill.html`.
  - `POST /` takes form fields `text` and `scenario_id`, grades the reply with `marking.mark_to_criteria`, and returns only the `grade_results.html` fragment. `static/drill.js` sends this POST with `fetch`, adds the reply as a sent bubble, disables the compose box, slides the phone into the left half and puts the fragment into `.results` in the right half.
- `app/marking.py`: turns each criterion string into a `noul` (yes/no probability) question named `q0`, `q1`, … and POSTs them to OpenRouter's alpha Decisions API (`https://openrouter.ai/api/alpha/decisions`, model `typesafe/jev-1.13`). Returns `list[tuple[criterion, bool]]`.
- `app/message.py`: a `Message` dataclass (`sender`, `text`). It is not used yet; templates currently read the raw scenario dicts.
- `app/templates/`: Jinja templates. `layout.html` is the base (blocks `title` and `main`), and the other templates extend it.
- `app/static/style.css`: plain CSS for the phone frame and chat bubbles (`.message.sent` / `.message.received`). `layout.html` has Bootstrap-style class names, but Bootstrap is not loaded.

## Conventions and gotchas

- **`app/` is a package.** Modules import each other relatively (`from .config import Config`, `from . import marking`). Run everything from the repo root as a module, for example `flask run`, `python -m app.app` or `python -m app.decisions_demo`. Running a file directly (`python app/app.py`) fails with "attempted relative import with no known parent package".
- The blueprint is imported inside `create_app()`, after config is set up. Keep it there.
- `marking.mark_to_criteria` pairs criteria with answers using `zip(criteria, answers.values())`, so it assumes the API returns answers in question order. Looking answers up by key (`answers[f"q{i}"]`) would be safer. The function also builds an unused `data` variable that duplicates the request body.
- The user's message is inserted straight into the model's `state` string, with no escaping.
- `app/__pycache__/*.pyc` is committed to git even though it shouldn't be. Don't add more.

## Scenarios (`scenarios/scenarios.json`)

```json
{ "scenarios": [ {
  "id": "unique-id001",
  "title": "Human-readable summary",
  "messages": [ { "sender": "contact" | "user", "text": "..." } ],
  "criteria": [ "offer to help", "..." ],
  "criteria_meta": { "model": "claude-haiku-4-5", "prompt_version": 1 }
} ] }
```

- `sender == "user"` renders as the player's (sent) bubble, and anything else renders as received.
- Criteria are short verb phrases. They get spliced into prompts as "Does the user <criterion> in this text message?" and "User does <criterion>", so write them to read naturally in that form.
- Scenarios are loaded once at startup. Restart the server (or rely on debug reload) after editing them.
