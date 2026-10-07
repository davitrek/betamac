import json
from pathlib import Path

import requests
from flask import current_app

from betamac.helpers import (
    scenario_criteria_to_dotpoint_str,
    scenario_id_to_str,
    scenario_to_str,
)

from .request_manager import (
    RequestWaitTooLongError,
    analysis_model_request_manager,
)


def fetch_answers(prompt: str, max_retries: int = 2) -> dict[dict] | None:
    # actually send API call (and any request logic, attempts, etc)
    for attempt in range(max_retries + 1):
        try:
            analysis_model_request_manager.wait_until_valid_request_time_or_throw()
        except RequestWaitTooLongError:
            return None

        response = requests.post(
            url=current_app.config["SCENE_CREATOR_API_URL"],
            headers={
                "Authorization": f"Bearer {current_app.config['OPENROUTER_SCENE_CREATOR_API_KEY']}",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "model": current_app.config["SCENE_CREATOR_MODEL"],
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    "reasoning": {"enabled": True},
                }
            ),
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

                analysis_model_request_manager.add_delay_to_next_request(
                    retry_after_sec
                )
                continue
            else:
                # other error codes
                print(response.status_code, ": ", response.reason)
                return None
        else:
            return response.json()

    return None
