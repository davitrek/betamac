import pytest

from betamac import create_app


@pytest.fixture
def app():
    # config.py runs load_dotenv(), which loads the real keys from .env.
    # these override config.py values
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            # Dummy keys make an accidental real API call fail with a 401.
            "OPENROUTER_JEV_API_KEY": "test-key",
            "OPENROUTER_SCENE_CREATOR_API_KEY": "test-key",
            # tests/test_rate_limits.py turns it on for its own app
            "RATELIMIT_ENABLED": False,
        }
    )

    with app.app_context():
        yield app
