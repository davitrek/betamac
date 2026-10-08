# CLAUDE.md

This file gives Claude Code guidance for working in this repository.

## What this is

A small Flask app for practising social text-message replies. The user sees a
phone-style chat from a scenario, types a reply, and an LLM grades the reply
against the scenario's criteria (pass/fail per criterion).

## Running

```sh
source .venv/bin/activate
pip install -r requirements.txt   # flask, flask-limiter, requests, python-dotenv, pytest, freezegun
flask run                         # from the repo root; .flaskenv sets FLASK_APP=betamac, FLASK_DEBUG=1
```

- `.env` (gitignored) should define `OPENROUTER_JEV_API_KEY`, `OPENROUTER_SCENE_CREATOR_API_KEY` and `SECRET_KEY`. `config.py` reads them with `environ.get`, so a missing value is `None` rather than an error. `create_app()` only prints "Missing API key". `SECRET_KEY` is required because `drill.py` uses the Flask `session`.
- VS Code: the "Python Debugger: Flask" launch config in `.vscode/launch.json` does the same thing under debugpy.
- Tests: `python -m pytest -q tests`. `tests/conftest.py` builds the app with `create_app({"TESTING": True, ...})`, dummy API keys and `RATELIMIT_ENABLED: False`. `tests/test_rate_limits.py` builds its own app with limiting on, and uses freezegun to move time forward. There's no linter or build step.

## Layout

- `betamac/__init__.py`: `create_app(test_config=None)` factory, which `flask run` finds through `FLASK_APP=betamac`. `test_config` is applied on top of `Config`. It wraps the app in `ProxyFix(x_for=1)`, calls `limiter.init_app(app)` and registers a 429 handler that returns `rate_limit_message()` as plain text (see "Rate limiting" below). Unless `TESTING` is set, it calls `configure_file_logger` for each JSONL log (see "Logging" below). Loads `scenarios/scenarios.json` into `app.config["SCENARIOS"]` (a dict keyed by scenario `id`) and `betamac/scenarios/scenario_review.json` into `app.config["SCENARIO_REVIEW"]`, then registers the `drill` and `scenarios` blueprints.
- `betamac/app.py`: empty leftover from the old `app/` layout.
- `betamac/config.py`: `Config` holds the API keys, `SECRET_KEY`, `JEV_API_URL` / `JEV_MODEL` (OpenRouter's alpha Decisions API, model `typesafe/jev-1.13`; see "Jev" below), `JEV_TRUE_THRESHOLD` (0.8, the probability cutoff for counting a `noul` as true), `SCENE_CREATOR_API_URL` / `SCENE_CREATOR_MODEL` (a chat-completions LLM used to write criteria for submitted scenarios), `REQUEST_DELAY_S`, `REQUEST_TIMEOUT_S`, the submission limits `POSSIBLE_SENDERS`, `MESSAGE_MAX_CHAR_LEN` and `SCENARIO_MAX_MESSAGES`, `ROOT_DIR` (the repo root) / `LOG_DIR` (`<repo>/logs`), and `LOG_MAX_BYTES` (5 MB) / `LOG_BACKUP_COUNT` (3) for log rotation, and the Flask-Limiter settings (`RATELIMIT_*`) and limit strings (`GRADING_LIMIT`, `SUBMISSION_*_LIMIT`).
- `betamac/drill.py`: blueprint `drill`.
  - `GET /` (endpoint `drill.drill`) picks a random scenario the user hasn't completed yet. It tracks completed ids in `session["seen_scenarios"]` and resets the list once every scenario has been seen. `drill.html` shows the phone and, 2rem to its right, a `.side` column as tall as the phone. The two are centred together as a pair. At its top is a "Context" box showing `problem_statement`, which is omitted when that's `""`. Below it is `.results`, and under that the Submit button (`.submit-reply`), which sits where Next scenario later appears.
  - `POST /grade` (endpoint `drill.grade`, limited to `GRADING_LIMIT` per IP, counting only 200 responses) takes JSON `{"scenario_id": ..., "messages": [text, ...]}`, joins the messages with newlines and grades them with `grading.grade_text_message`, adds the scenario to `seen_scenarios`, and returns only the `grade_results.html` fragment. It returns 400 for bad input (including an empty list or a blank message) and 500 if grading returns `None`.
- `betamac/grading.py`: `grade_text_message` (stubbed, see below) calls `jev_grade`, which turns each criterion into a `noul` (yes/no probability) question named `q0`, `q1`, …, sends them through `integrations.jev.fetch_answers` and returns `dict[criterion, bool]`, or `None` if Jev fails or an answer is missing. Answers are looked up by key (`q{i}`). Every `jev_grade` call logs one record to the `betamac.grading` logger.
- `betamac/limiter.py`: the shared Flask-Limiter instance (keyed by client IP), `global_key` for limits shared by every client, `outcome_is(outcome)` for `deduct_when`, and `rate_limit_message()` for the 429 text.
- `betamac/helpers.py`: formats scenarios (problem statement, messages, criteria) as strings for prompts and Jev `state`.
- `betamac/integrations/jev.py`: `fetch_answers(state, questions)` POSTs to the Decisions API and returns the parsed JSON, or `None` on any non-429 error or when retries run out. A 429 delays the next request by `retry-after` (falling back to `2**attempt` seconds when the header is missing) and retries.
- `betamac/integrations/analysis_model.py`: the same retry wrapper for the chat-completions "scene creator" LLM.
- `betamac/integrations/request_manager.py`: `RequestManager` (singletons `jev_request_manager` and `analysis_model_request_manager`) spaces requests by `REQUEST_DELAY_S`, applies `retry-after` delays after a 429, and raises `RequestWaitTooLongError` when the wait would be longer than `REQUEST_TIMEOUT_S`.
- `betamac/scenarios/`: blueprint `scenarios`.
  - `scenarios.py`: `GET /new-scenario` (endpoint `scenarios.create_new`) renders `new_scenario.html`. `POST /submit-scenario` (endpoint `scenarios.submit`) takes JSON `{"messages": [[sender, text], ...], "problem_statement": "..."}`. It validates the input (allowed senders, no blank text, length limits, last message not from `user`, at least one `contact` message), runs `jev_review` to moderate it, has the LLM write criteria with `create_new_scenario`, and appends the result to `scenarios/scenarios.json`. It `flash()`es the outcome and returns 204, 400 if the input is invalid, 500 if `jev_review` or `create_new_scenario` raises `ValueError`, or 429 when rate limited. `save_scenario` does the file write (tests patch it out).
  - `scenario_review.py`: `jev_review(problem_statement, messages)` is the automated moderation gate (see "Jev" below). It asks the questions in `scenario_review.json` (the context-agreement question only when there is a problem statement), and `jev_response_breakdown` applies each question's own `threshold` and `reject_if` (`"above"` / `"below"`). It returns `True` if no question rejects the scenario and `False` otherwise, and raises `ValueError` when Jev fails or an answer is missing (so an outage is never treated as a rejection). Every call logs one record to the `betamac.scenarios.scenario_review` logger. `create_new_scenario` asks the LLM (prompt in `scenario_criteria_creation_prompt`, plus five existing scenarios as few-shot examples) for an id and a list of criteria.
- `betamac/templates/`: Jinja templates. `layout.html` is the base: a `<nav class="navbar">` (brand link to `/` and a "Submit scenario" pill linking to `/new-scenario`), and the blocks `title`, `flashes` and `main`. By default `flashes` shows flashed messages above `main`. `new_scenario.html` empties it and shows them in bold under its buttons instead. `drill.html`, `grade_results.html` and `new_scenario.html` extend or fill into it.
- `betamac/static/drill.js`: the compose form's send button (or Enter) only adds a sent bubble and appends the text to `sentMessages`. Nothing is posted yet, and whitespace-only messages are skipped. Submit (disabled until one message has been sent) hides itself, disables the form, POSTs the JSON to `data-url` with `data-scenario-id`, adds `.graded` to `.drill` (the `.results` column under the context box fades in) and puts the fragment into `.results-body`. It then shows the `.next-scenario` button, which reloads `/`. Shift+Enter adds a newline. After a successful grading it stores the time in `localStorage["lastGradedAt"]`, and Submit stays disabled (tooltip "Please wait before submitting again") until 5 seconds have passed, including across the reload. On a 429 it shows the server's message and re-enables Submit and the form.
- `betamac/static/new_scenario.js`: builds message rows (sender `<select>`, text `<input>` and an X remove button) from the `<template id="message-row">` element. The + button adds a row, and the X on the last remaining row is disabled. Submit POSTs JSON `{"messages": [[sender, text], ...]}` to the form's `action` (`scenarios.submit`), and reloads the page on success so the flashed message shows. On failure the rows are kept, and a 400 or 429 response's text is shown in `.form-response`.
- `betamac/static/style.css`: plain CSS, with no framework loaded. It covers the phone frame, the chat bubbles (`.message.sent` / `.message.received`), the navbar, and a shared `.pill` button class. `.next-scenario` and `.submit-reply` are JavaScript hooks, and `.pill` does the styling (`.pill:disabled` is dimmed). Drill layout: `.context` (a `.side-heading` label over the bubble) fits its text up to a third of the phone's height (75vh / 3), and its bubble scrolls beyond that. `.results` sits 1.5rem below it and fills the rest of the column. Inside it, `.grading` holds a "Grading" `.side-heading` over `.results-body`, which grows and scrolls, and the Next scenario button is pinned to the bottom, level with the phone's bottom edge.

## Conventions and gotchas

- **`betamac/` is a package.** Modules import each other relatively (`from .config import Config`, `from . import grading`). Run things from the repo root as a module, never by file path.
- The blueprints are imported inside `create_app()`, after config is set up. Keep them there.
- **Grading is currently stubbed.** `grade_text_message` returns `testing_sentinel_answers(...)` straight away, so `jev_grade` doesn't run and nothing is written to `grading.jsonl`. Remove that early return to grade for real.
- User-written text (drill replies and submitted scenarios) is inserted straight into the Jev `state` string, with no escaping or structure separating it from our own framing text.
- In `style.css`, don't give `.pill` a `display` value. It would override the `hidden` attribute on the Submit and Next scenario buttons.
- `__pycache__` is gitignored. Stale `.pyc` files from deleted modules may still be on disk, but they're harmless.

## Logging

Each Jev call is logged as one JSON line, for tuning thresholds later (e.g. with `scripts/review_eval.py`).

- Modules use `logger = logging.getLogger(__name__)` and log `json.dumps(record, ensure_ascii=False)`: INFO for a normal outcome, ERROR for a Jev failure.
- `configure_file_logger(logger_name, log_path, max_bytes, backup_count)` in `betamac/__init__.py` gives a logger level INFO and a UTF-8 `RotatingFileHandler` whose formatter outputs only the message, so every line parses with `json.loads`. It skips adding the handler if one already writes to that path, because loggers are process-wide and `create_app()` can run more than once in a process.
- A log rotates at `LOG_MAX_BYTES` into `<name>.jsonl.1` … `.3` (`.1` is the newest), and the oldest records are deleted. Read `<name>.jsonl*` to get all of them. `RotatingFileHandler` isn't safe across processes: with several gunicorn workers, rotations can clash and records may go to a rotated file or be lost. That's accepted for now.
- Files in `LOG_DIR`:
  - `scenario_review.jsonl` (from `jev_review`): `time`, `problem_statement`, `messages`, `jev_response_id`, `jev_cost`, `review_questions` (`{name: {noul, threshold, reject_if, rejected}}`) and `outcome` (`accepted` / `rejected` / `error`, plus an `error` string).
  - `grading.jsonl` (from `jev_grade`): `time`, `scenario_id`, `user_response`, `jev_response_id`, `jev_cost`, `criteria` (`{criterion: {question, noul, threshold, met}}`) and `outcome` (`graded` / `error`, plus an `error` string).
- Each module has its own logger and file. Don't attach a handler to the parent `betamac` logger (it would merge the files), and don't set `propagate = False` (pytest's `caplog` listens on the root logger).
- Tests set `TESTING`, so no file handlers are added and tests never write to `logs/`. They check records through `caplog`.
- **Records contain user-written text verbatim. `logs/` must stay gitignored.**

## Rate limiting

Flask-Limiter, configured in `Config` and `betamac/limiter.py`. Clients are identified by IP.

- `ProxyFix(x_for=1)` takes the client IP from the `X-Forwarded-For` header that nginx sets. Without a proxy the header is absent and `remote_addr` is used. A client that can reach the app directly could fake the header, which is accepted because the app only runs unproxied on a trusted local network. When deployed, only nginx should be able to reach the app.
- `RATELIMIT_STRATEGY = "moving-window"`: each charge expires one window after it was made (a rolling hour, not a clock hour).
- Every limit uses `deduct_when`. It is only checked before the view and charged afterwards if the response or `g.outcome` says so. Bad input and Jev or Deepseek failures are never charged.
  - `/grade`: `GRADING_LIMIT` (1 per 5 s), charged on a 200.
  - `/submit-scenario`: `SUBMISSION_REJECTED_LIMIT` (3/hour) is charged when Jev rejects (`g.outcome = "rejected"`). `SUBMISSION_ACCEPTED_LIMIT` (1/hour) and `SUBMISSION_GLOBAL_LIMIT` (20/day, keyed by `global_key` so all IPs share it) are charged when Deepseek has written the criteria (`g.outcome = "accepted"`). A Deepseek success locks the IP out for a full hour, because it has its own limit and isn't a cost charged against the 3/hour one.
- `RATELIMIT_FAIL_ON_FIRST_BREACH = False` evaluates every limit on the route, so `rate_limit_message()` can see when the global cap is hit. That message ("Submission limit reached, try again tomorrow") takes priority over the per-IP one ("Try again in N minutes").
- `RATELIMIT_STORAGE_URI = "memory://"`: the counters are per process and reset on every restart (including a debug reload). With several gunicorn workers, switch it to Redis so they share counts.
- `limiter` is a module-level singleton, and `init_app` reads `RATELIMIT_ENABLED` from whichever app was built last. Don't build two apps in one test.

## Jev (TypeSafe decision model)

Jev is used both to grade replies and to moderate submitted scenarios. **Moderation of user-submitted scenarios is meant to be fully automated through Jev**, with no human review, so treat changes to `jev_review` and its questions as safety-critical.

**Jev is not a chat model.** It doesn't generate text or explain its answers. You send it a `state` (the thing being judged) plus named, typed questions, and it returns a calibrated answer for each question. Prompts and parsing that suit chat models don't apply.

Request (`POST https://openrouter.ai/api/alpha/decisions`, `Authorization: Bearer <key>`):

```json
{
  "model": "typesafe/jev-1.13",
  "state": "string, OR a JSON object/array",
  "questions": {
    "some_name": {
      "type": "noul",
      "instructions": "Is <condition> true?",
      "criteria": { "true": "what the true case looks like", "false": "what the false case looks like" }
    },
    "other_name": { "type": "choice", "instructions": "...", "criteria": { "option_a": "...", "option_b": "..." } },
    "third_name": { "type": "score",  "instructions": "...", "criteria": ["lowest level", "...", "highest level"] }
  }
}
```

Response: `{"id", "model", "provider", "answers": {<name>: ...}, "usage": {"input_tokens", "output_tokens", "cost"}}`.
- `noul` answer: `{"type": "noul", "noul": p}`, where `p` is P(true) in 0–1. It has no separate confidence. 0.5 means genuinely uncertain.
- `choice` answer: `{"choice", "confidence", "probabilities": {option: p}}`.
- `score` answer: `{"score", "confidence", "probabilities": {index: p}, "legend"}`. The score is a probability-weighted position on the ordered scale.

How to write questions:
- **The question name (key) is never shown to the model.** Only `instructions` and `criteria` are, so they must carry all of the meaning.
- `instructions` frames the question, ideally as an actual question. `criteria` describe each outcome. Describe both sides positively and concretely, the way you'd brief a new hire. A bare negation ("No, it does not") gives the model nothing to match against.
- `state`, `instructions` and criteria values can each be a string, object or array. An object `state` (e.g. `{"context": ..., "messages": [...]}`) lets instructions refer to fields by name in backticks, and keeps user-written text separate from our framing. Criteria can be objects such as `{"what": "...", "examples": [...]}`. Community benchmarks found that adding examples to criteria greatly sharpened results on borderline cases.
- Questions in one request are independent and evaluated in parallel. Batch every check on the same state into one call rather than making several calls.
- `choice` is for mutually exclusive outcomes. For flags that can co-occur (e.g. moderation reasons), use separate `noul` questions.

Thresholds and calibration:
- Probabilities are calibrated in aggregate, not per call, and they wobble slightly between identical calls. Treat a value near 0.5 as a third outcome ("unsure"), not as a weak yes or no.
- TypeSafe advises picking thresholds from the cost of each kind of mistake and from labelled data, not from a round number. Different questions can and should have different thresholds and directions. The current `JEV_TRUE_THRESHOLD = 0.8` is shared by everything.
- The model is pinned to `typesafe/jev-1.13` so that tuned thresholds stay valid. `~typesafe/jev-latest` exists but drifts.

Limits and cost: a 32k-token context window, and text input only. Billing is by input tokens only (about $0.042/M), and output is free. The latency is about 0.5s. Errors use the standard OpenRouter codes (400, 401, 402 out of credits, 413 too large, 429 rate limited, 5xx/524/529 upstream). `jev.fetch_answers` retries only on 429, and returns `None` on other errors.

Docs: https://openrouter.ai/docs/guides/community/jev-tutorial , https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request , https://openrouter.ai/blog/insights/what-is-jev/

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
