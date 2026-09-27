import json
import os
from pathlib import Path

from flask import Flask

from .config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    with open(
        Path(__file__).resolve().parent.parent / "scenarios" / "scenarios.json"
    ) as f:
        app.config["SCENARIOS"] = {
            s["id"]: s for s in json.load(f)["scenarios"]
        }

    # ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    from . import drill

    app.register_blueprint(drill.bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
