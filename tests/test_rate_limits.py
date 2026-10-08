import pytest
from freezegun import freeze_time

from betamac import create_app, grading
from betamac.limiter import limiter
from betamac.scenarios import scenarios

# Must be in the future. The limiter's in-memory storage clears expired
# entries from a threading.Timer, and freezegun gives threading the real
# time, so entries made at a past frozen time could be wiped mid-test.
START = "2100-01-01 12:00:00"

VALID_SCENARIO = {
    "problem_statement": "",
    "messages": [["contact", "Hey, how are you?"]],
}


@pytest.fixture
def limited_app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "OPENROUTER_JEV_API_KEY": "test-key",
            "OPENROUTER_SCENE_CREATOR_API_KEY": "test-key",
            "RATELIMIT_ENABLED": True,
        }
    )
    limiter.reset()

    with app.app_context():
        yield app

    limiter.reset()


@pytest.fixture
def client(limited_app):
    return limited_app.test_client()


@pytest.fixture
def scenario_id(limited_app):
    return next(iter(limited_app.config["SCENARIOS"]))


def post_grade(client, scenario_id, ip="1.1.1.1", headers=None):
    return client.post(
        "/grade",
        json={"scenario_id": scenario_id, "messages": ["hello"]},
        environ_base={"REMOTE_ADDR": ip},
        headers=headers,
    )


def post_scenario(client, ip="1.1.1.1", data=VALID_SCENARIO):
    return client.post(
        "/submit-scenario", json=data, environ_base={"REMOTE_ADDR": ip}
    )


@pytest.fixture
def grading_ok(monkeypatch):
    monkeypatch.setattr(
        grading, "grade_text_message", lambda message, sid: {"criterion": True}
    )


@pytest.fixture
def grading_fails(monkeypatch):
    monkeypatch.setattr(
        grading, "grade_text_message", lambda message, sid: None
    )


@pytest.fixture
def review(monkeypatch):
    """Mocks Jev review, Deepseek and the scenarios.json write.

    Set review.outcome to "accept", "reject" or "jev_error", and
    review.deepseek_fails to make create_new_scenario raise."""

    class Review:
        outcome = "accept"
        deepseek_fails = False
        saved = []

    r = Review()

    def fake_jev_review(problem_statement, messages):
        if r.outcome == "jev_error":
            raise ValueError("Jev failed")
        return r.outcome == "accept"

    def fake_create_new_scenario(problem_statement, messages):
        if r.deepseek_fails:
            raise ValueError("Deepseek failed")
        return {
            "id": "test-id-001",
            "problem_statement": "",
            "messages": [{"sender": "contact", "text": "hey"}],
            "criteria": ["express sympathy"],
        }

    monkeypatch.setattr(scenarios, "jev_review", fake_jev_review)
    monkeypatch.setattr(
        scenarios, "create_new_scenario", fake_create_new_scenario
    )
    monkeypatch.setattr(
        scenarios, "save_scenario", lambda p, s: r.saved.append(s)
    )
    return r


# ---------------- grading: 1 per 5 seconds per IP ----------------


def test_second_grading_within_5s_is_limited(client, scenario_id, grading_ok):
    with freeze_time(START):
        assert post_grade(client, scenario_id).status_code == 200
        response = post_grade(client, scenario_id)
        assert response.status_code == 429
        assert "Slow down, try again in a few seconds" in response.text


def test_grading_allowed_again_after_5s(client, scenario_id, grading_ok):
    with freeze_time(START) as frozen:
        assert post_grade(client, scenario_id).status_code == 200
        frozen.tick(4)
        assert post_grade(client, scenario_id).status_code == 429
        frozen.tick(2)
        assert post_grade(client, scenario_id).status_code == 200


def test_invalid_grading_request_does_not_count(
    client, scenario_id, grading_ok
):
    with freeze_time(START):
        bad = client.post(
            "/grade",
            json={"scenario_id": scenario_id, "messages": []},
            environ_base={"REMOTE_ADDR": "1.1.1.1"},
        )
        assert bad.status_code == 400
        assert post_grade(client, scenario_id).status_code == 200


def test_failed_grading_does_not_count(
    client, scenario_id, grading_fails, monkeypatch
):
    with freeze_time(START):
        assert post_grade(client, scenario_id).status_code == 500
        monkeypatch.setattr(
            grading, "grade_text_message", lambda message, sid: {"c": True}
        )
        assert post_grade(client, scenario_id).status_code == 200


def test_grading_limit_is_per_ip(client, scenario_id, grading_ok):
    with freeze_time(START):
        assert post_grade(client, scenario_id, ip="1.1.1.1").status_code == 200
        assert post_grade(client, scenario_id, ip="2.2.2.2").status_code == 200
        assert post_grade(client, scenario_id, ip="1.1.1.1").status_code == 429


def test_x_forwarded_for_is_used_as_client_ip(client, scenario_id, grading_ok):
    # ProxyFix: behind nginx every request comes from the proxy's address,
    # and X-Forwarded-For carries the real client
    with freeze_time(START):
        a = {"X-Forwarded-For": "9.9.9.9"}
        b = {"X-Forwarded-For": "8.8.8.8"}
        assert post_grade(client, scenario_id, headers=a).status_code == 200
        assert post_grade(client, scenario_id, headers=b).status_code == 200
        assert post_grade(client, scenario_id, headers=a).status_code == 429


# ------------- scenario submission: per IP, rolling hour -------------


def test_invalid_submissions_do_not_count(client, review):
    with freeze_time(START):
        for _ in range(5):
            assert (
                post_scenario(client, data={"messages": []}).status_code == 400
            )
        assert post_scenario(client).status_code == 204
        assert review.saved == [
            {
                "id": "test-id-001",
                "problem_statement": "",
                "messages": [{"sender": "contact", "text": "hey"}],
                "criteria": ["express sympathy"],
            }
        ]


def test_jev_errors_do_not_count(client, review):
    with freeze_time(START):
        review.outcome = "jev_error"
        for _ in range(5):
            assert post_scenario(client).status_code == 500
        review.outcome = "accept"
        assert post_scenario(client).status_code == 204


def test_deepseek_failure_does_not_count(client, review):
    with freeze_time(START):
        review.deepseek_fails = True
        assert post_scenario(client).status_code == 500
        review.deepseek_fails = False
        assert post_scenario(client).status_code == 204


def test_two_rejections_leave_a_third_attempt(client, review):
    with freeze_time(START):
        review.outcome = "reject"
        assert post_scenario(client).status_code == 204
        assert post_scenario(client).status_code == 204
        review.outcome = "accept"
        assert post_scenario(client).status_code == 204


def test_three_rejections_lock_out(client, review):
    with freeze_time(START):
        review.outcome = "reject"
        for _ in range(3):
            assert post_scenario(client).status_code == 204
        assert post_scenario(client).status_code == 429


def test_reaching_deepseek_locks_out_immediately(client, review):
    with freeze_time(START):
        assert post_scenario(client).status_code == 204
        review.outcome = "reject"
        assert post_scenario(client).status_code == 429


def test_rejections_then_deepseek_locks_out(client, review):
    with freeze_time(START):
        review.outcome = "reject"
        assert post_scenario(client).status_code == 204
        assert post_scenario(client).status_code == 204
        review.outcome = "accept"
        assert post_scenario(client).status_code == 204
        assert post_scenario(client).status_code == 429


def test_deepseek_lockout_lasts_a_full_hour(client, review):
    # rolling hour: a rejection at minute 0 expiring at minute 60 must not
    # free the user when they reached Deepseek at minute 50
    with freeze_time(START) as frozen:
        review.outcome = "reject"
        assert post_scenario(client).status_code == 204
        frozen.tick(50 * 60)
        review.outcome = "accept"
        assert post_scenario(client).status_code == 204
        frozen.tick(15 * 60)  # minute 65
        assert post_scenario(client).status_code == 429
        frozen.tick(46 * 60)  # minute 111, an hour after Deepseek
        assert post_scenario(client).status_code == 204


def test_rejections_roll_off_after_an_hour(client, review):
    with freeze_time(START) as frozen:
        review.outcome = "reject"
        assert post_scenario(client).status_code == 204  # minute 0
        frozen.tick(10 * 60)
        assert post_scenario(client).status_code == 204  # minute 10
        assert post_scenario(client).status_code == 204  # minute 10
        assert post_scenario(client).status_code == 429
        frozen.tick(51 * 60)  # minute 61: only the minute-0 one has expired
        assert post_scenario(client).status_code == 204
        assert post_scenario(client).status_code == 429


def test_submission_limit_is_per_ip(client, review):
    with freeze_time(START):
        assert post_scenario(client, ip="1.1.1.1").status_code == 204
        assert post_scenario(client, ip="2.2.2.2").status_code == 204
        assert post_scenario(client, ip="1.1.1.1").status_code == 429


def test_lockout_message_gives_minutes_left(client, review):
    with freeze_time(START) as frozen:
        assert post_scenario(client).status_code == 204
        frozen.tick(18 * 60)
        response = post_scenario(client)
        assert response.status_code == 429
        assert response.text == (
            "You can submit one scenario per hour. Try again in 42 minutes."
        )


def test_locked_out_user_gets_429_for_invalid_input(client, review):
    with freeze_time(START):
        assert post_scenario(client).status_code == 204
        assert post_scenario(client, data={"messages": []}).status_code == 429


# ---------------- scenario submission: global 20/day ----------------


def test_global_cap_after_20_deepseek_submissions(client, review):
    with freeze_time(START):
        for i in range(20):
            assert post_scenario(client, ip=f"10.0.0.{i}").status_code == 204
        response = post_scenario(client, ip="10.0.1.1")
        assert response.status_code == 429
        assert response.text == "Submission limit reached, try again tomorrow"


def test_rejections_do_not_count_towards_global_cap(client, review):
    with freeze_time(START):
        review.outcome = "reject"
        for i in range(25):
            assert post_scenario(client, ip=f"10.0.0.{i}").status_code == 204
        review.outcome = "accept"
        assert post_scenario(client, ip="10.0.1.1").status_code == 204


def test_global_message_wins_when_both_limits_hit(client, review):
    with freeze_time(START):
        for i in range(19):
            assert post_scenario(client, ip=f"10.0.0.{i}").status_code == 204
        assert post_scenario(client, ip="1.1.1.1").status_code == 204
        response = post_scenario(client, ip="1.1.1.1")
        assert response.status_code == 429
        assert response.text == "Submission limit reached, try again tomorrow"


def test_global_cap_resets_after_a_day(client, review):
    with freeze_time(START) as frozen:
        for i in range(20):
            assert post_scenario(client, ip=f"10.0.0.{i}").status_code == 204
        frozen.tick(24 * 60 * 60 + 1)
        assert post_scenario(client, ip="10.0.1.1").status_code == 204


# ---------------- bug fix ----------------


def test_non_json_submission_is_400(client, review):
    response = client.post(
        "/submit-scenario", data="not json", content_type="text/plain"
    )
    assert response.status_code == 400


# ---------------- disabled in the normal test config ----------------


def test_limits_disabled_in_test_config(app, grading_ok):
    # `app` (conftest) sets RATELIMIT_ENABLED = False. Doesn't use the
    # limited_app-based fixtures: the limiter is shared, so building a second
    # app would turn limiting back on.
    client = app.test_client()
    scenario_id = next(iter(app.config["SCENARIOS"]))
    for _ in range(3):
        assert post_grade(client, scenario_id).status_code == 200
