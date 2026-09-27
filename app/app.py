from config import Config
from flask import Flask, jsonify


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.get("/")
    def index():
        return jsonify(status="ok")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
