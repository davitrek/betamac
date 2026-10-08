import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .limiter import limiter, rate_limit_message
from .scenarios.scenario_management import is_scenarios_valid, load_scenarios


def configure_file_logger(
    logger_name: str, log_path: Path, max_bytes: int, backup_count: int
):
    # one JSONL file per logger, rotated at max_bytes. Records are already JSON
    # strings, so the formatter outputs only the message
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # skip adding handler if it alr exists (create_app can run more than once
    # per process, and loggers are process-wide)
    for lh in logger.handlers:
        if isinstance(lh, logging.FileHandler) and lh.baseFilename == str(
            log_path
        ):
            return

    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(file_handler)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.from_mapping(test_config)

    # Behind nginx, take the client IP from X-Forwarded-For (needed for the
    # per-IP rate limits). Without a proxy the header is absent and nothing
    # changes. The header could be spoofed if the app were reachable directly,
    # which is accepted on a trusted local network.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

    limiter.init_app(app)

    @app.errorhandler(429)
    def rate_limited(e):
        return rate_limit_message(), 429

    # do not configure loggers for tests (they use caplog instead)
    if not app.config.get("TESTING"):
        for logger_name, file_name in [
            ("betamac.scenarios.scenario_review", "scenario_review.jsonl"),
            ("betamac.grading", "grading.jsonl"),
        ]:
            configure_file_logger(
                logger_name,
                app.config["LOG_DIR"] / file_name,
                app.config["LOG_MAX_BYTES"],
                app.config["LOG_BACKUP_COUNT"],
            )

    if (
        not app.config["OPENROUTER_JEV_API_KEY"]
        or not app.config["OPENROUTER_SCENE_CREATOR_API_KEY"]
    ):
        print("Missing API key")

    app.config["SCENARIOS"] = load_scenarios(app.config["SCENARIOS_PATH"])

    if not is_scenarios_valid(
        app.config["SCENARIOS"], app.config["POSSIBLE_SENDERS"]
    ):
        print("One or more scenarios are malformed!")

    with open(
        Path(__file__).resolve().parent / "scenarios" / "scenario_review.json"
    ) as f:
        app.config["SCENARIO_REVIEW"] = json.load(f)

    from . import drill

    app.register_blueprint(drill.bp)

    from .scenarios import scenarios

    app.register_blueprint(scenarios.bp)

    return app
