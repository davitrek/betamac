import pytest
import requests

from betamac.integrations import jev, request_manager


class FakeResponse:
    def __init__(self, status_code, body=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.reason = "fake"
        self._body = body

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


ANSWERS = {"answers": {"q0": {"type": "noul", "noul": 0.9}}}


@pytest.fixture
def fake_post(app, monkeypatch):
    """Replace requests.post with one that returns the given responses in order."""
    # jev_request_manager is a singleton, so reset its state and skip real sleeps
    monkeypatch.setattr(jev.jev_request_manager, "next_valid_request_time", 0)
    monkeypatch.setattr(request_manager, "sleep", lambda seconds: None)

    calls = []

    def set_responses(*responses):
        remaining = iter(responses)

        def post(**kwargs):
            calls.append(kwargs)
            return next(remaining)

        monkeypatch.setattr(jev.requests, "post", post)
        return calls

    return set_responses


def test_fetch_answers_success(fake_post):
    calls = fake_post(FakeResponse(200, ANSWERS))

    output = jev.fetch_answers("state", {"q0": {}})

    assert output == ANSWERS
    assert len(calls) == 1
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"


def test_fetch_answers_retries_after_429(fake_post):
    calls = fake_post(
        FakeResponse(429, headers={"retry-after": "1"}),
        FakeResponse(200, ANSWERS),
    )

    output = jev.fetch_answers("state", {})

    assert output == ANSWERS
    assert len(calls) == 2


def test_fetch_answers_429_without_retry_after(fake_post):
    calls = fake_post(FakeResponse(429), FakeResponse(200, ANSWERS))

    output = jev.fetch_answers("state", {})

    assert output == ANSWERS
    assert len(calls) == 2


@pytest.mark.parametrize("status_code", [400, 401, 402, 500])
def test_fetch_answers_other_error(fake_post, status_code):
    calls = fake_post(FakeResponse(status_code))

    output = jev.fetch_answers("state", {})

    assert output is None
    assert len(calls) == 1


def test_fetch_answers_retries_exhausted(fake_post):
    calls = fake_post(
        FakeResponse(429, headers={"retry-after": "1"}),
        FakeResponse(429, headers={"retry-after": "1"}),
        FakeResponse(429, headers={"retry-after": "1"}),
    )

    output = jev.fetch_answers("state", {}, max_retries=2)

    assert output is None
    assert len(calls) == 3


def test_fetch_answers_wait_too_long(fake_post, app):
    too_long = str(app.config["REQUEST_TIMEOUT_S"] + 10)
    calls = fake_post(
        FakeResponse(429, headers={"retry-after": too_long}),
        FakeResponse(200, ANSWERS),
    )

    output = jev.fetch_answers("state", {})

    assert output is None
    assert len(calls) == 1
