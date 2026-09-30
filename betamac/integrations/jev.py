import json

import requests
from flask import current_app

from .request_manager import RequestWaitTooLongError, jev_request_manager


def fetch_answers(
    state: str, questions: dict, max_retries: int = 2
) -> dict[dict] | None:
    # actually send API call (and any request logic, attempts, etc)
    for attempt in range(max_retries + 1):
        try:
            jev_request_manager.wait_until_valid_request_time_or_throw()
        except RequestWaitTooLongError:
            return None

        response = requests.post(
            url=current_app.config["JEV_API_URL"],
            headers={
                "Authorization": f"Bearer {current_app.config['OPENROUTER_JEV_API_KEY']}",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "model": current_app.config["JEV_MODEL"],
                    "state": state,
                    "questions": questions,
                }
            ),
            timeout=current_app.config["REQUEST_TIMEOUT_S"],
        )

        try:
            response.raise_for_status()
        except requests.HTTPError:
            # rate limited, call function again after delay
            if response.status_code == 429:
                retry_after_sec = int(response.headers.get("retry-after", 0))

                if not retry_after_sec:
                    retry_after_sec = (
                        2**attempt
                    )  # exponential backoff as backup

                jev_request_manager.add_delay_to_next_request(retry_after_sec)
                continue
            else:
                # other error codes
                print(response.status_code, ": ", response.reason)
                return None
        else:
            return response.json()

    return None
