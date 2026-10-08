from os import environ
from pathlib import Path

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

    JEV_GRADING_SUCCESS_THRESHOLD = 0.8

    REQUEST_DELAY_S = 0.1
    REQUEST_TIMEOUT_S = 5

    # "user" must always be first in this tuple
    POSSIBLE_SENDERS = ("user", "contact")
    MESSAGE_MAX_CHAR_LEN = 160
    SCENARIO_MAX_MESSAGES = 10

    # Flask-Limiter (see betamac/limiter.py). Counters live in this process's
    # memory, so they reset on restart and aren't shared between gunicorn
    # workers. Use e.g. "redis://localhost:6379" to share them.
    RATELIMIT_STORAGE_URI = "memory://"
    # rolling windows: each charge expires one window after it was made
    RATELIMIT_STRATEGY = "moving-window"
    # check every limit on a route (not just the first breached one), so the
    # 429 message can tell when the global cap is hit
    RATELIMIT_FAIL_ON_FIRST_BREACH = False
    GRADING_LIMIT = "1 per 5 seconds"
    # per IP: Jev rejections, and submissions that reached Deepseek
    SUBMISSION_REJECTED_LIMIT = "3 per hour"
    SUBMISSION_ACCEPTED_LIMIT = "1 per hour"
    # across all IPs: submissions that reached Deepseek
    SUBMISSION_GLOBAL_LIMIT = "20 per day"

    ROOT_DIR = Path(__file__).parent.parent
    LOG_DIR = ROOT_DIR / "logs"
    SCENARIOS_PATH = ROOT_DIR / "scenarios" / "scenarios.json"

    # each log rotates at LOG_MAX_BYTES and keeps LOG_BACKUP_COUNT old files
    # (<name>.jsonl.1 is the newest), so about 20MB per log at most
    LOG_MAX_BYTES = 5 * 1024 * 1024
    LOG_BACKUP_COUNT = 3
