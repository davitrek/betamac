import math
import time

from flask import g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Keyed by client IP. Behind nginx, ProxyFix (in create_app) makes
# remote_addr the real client rather than the proxy.
limiter = Limiter(key_func=get_remote_address)

# key for limits shared by every client
GLOBAL_KEY = "global"


def global_key() -> str:
    return GLOBAL_KEY


# Views set g.outcome so a limit is only charged for what actually happened.
# Anything that never reaches (or fails at) Jev/Deepseek leaves it unset, so
# nothing is charged.
def outcome_is(outcome: str):
    return lambda response: g.get("outcome") == outcome


def rate_limit_message() -> str:
    # limits evaluated for this request, smallest window first
    breached = [lim for lim in limiter.current_limits if lim.breached]

    if any(lim.request_args[-2] == GLOBAL_KEY for lim in breached):
        return "Submission limit reached, try again tomorrow"

    if not breached or breached[0].limit.get_expiry() < 60:
        return "Slow down, try again in a few seconds"

    # window[0] is when the oldest charge expires (rolling window). If both
    # per-IP limits are full, the user waits for the later one.
    reset_at = max(lim.window[0] for lim in breached)
    minutes = max(1, math.ceil((reset_at - time.time()) / 60))
    return (
        "You can submit one scenario per hour. "
        f"Try again in {minutes} minute{'' if minutes == 1 else 's'}."
    )
