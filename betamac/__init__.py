import json
from pathlib import Path

from flask import Flask

from .config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    if (
        not app.config["OPENROUTER_JEV_API_KEY"]
        or not app.config["OPENROUTER_SCENE_CREATOR_API_KEY"]
    ):
        print("Missing API key")

    with open(
        Path(__file__).resolve().parent.parent / "scenarios" / "scenarios.json"
    ) as f:
        app.config["SCENARIOS"] = {
            s["id"]: s
            for s in json.load(f)["scenarios"]
            # ideally would check validity of keys here
            # -> each scenario needs a "criteria", "messages", etc.
            # ---> ensure these exist & spelling of keys is correct
        }

    from . import drill

    app.register_blueprint(drill.bp)

    from .scenarios import scenarios

    app.register_blueprint(scenarios.bp)

    return app
