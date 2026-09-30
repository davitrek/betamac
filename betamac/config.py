from os import environ

from dotenv import load_dotenv

load_dotenv()


class Config:
    JEV_API_URL = "https://openrouter.ai/api/alpha/decisions"
    JEV_MODEL = "typesafe/jev-1.13"
    OPENROUTER_JEV_API_KEY = environ.get("OPENROUTER_JEV_API_KEY")

    SCENE_CREATOR_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    SCENE_CREATOR_MODEL = "deepseek/deepseek-v4.1-flash"
    OPENROUTER_SCENE_CREATOR_API_KEY = environ.get(
        "OPENROUTER_SCENE_CREATOR_API_KEY"
    )

    SECRET_KEY = environ.get("SECRET_KEY")

    JEV_TRUE_THRESHOLD = 0.8

    REQUEST_DELAY_S = 0.1
    REQUEST_TIMEOUT_S = 5

    POSSIBLE_SENDERS = ("user", "contact")
    MESSAGE_MAX_CHAR_LEN = 160
    SCENARIO_MAX_MESSAGES = 10
