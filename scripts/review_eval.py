"""Run scenarios through the Jev review questions to help tune thresholds.

Sends every scenario in scenarios/scenarios.json (all expected to pass) and
every case in scripts/review_cases.json (each lists the questions it should
fail) through the same Jev request that jev_review makes. Each question's
noul is compared to its threshold in scenario_review.json and to what the
case expects.

Run from the repo root (makes real, billed API calls):

    python -m scripts.review_eval              # everything, once
    python -m scripts.review_eval --repeats 3  # see how much nouls wobble
    python -m scripts.review_eval --only cases # or: --only scenarios

Each run writes to scripts/review_eval_runs/<timestamp>/:
    responses.jsonl  the raw Jev response for every call
    results.csv      one row per (case, repeat, question), for offline tuning
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from flask import current_app

from betamac import create_app
from betamac.integrations import jev
from betamac.scenarios.scenario_review import (
    build_jev_questions,
    build_jev_state,
    is_question_rejected,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_PATH = REPO_ROOT / "scenarios" / "scenarios.json"
CASES_PATH = Path(__file__).resolve().parent / "review_cases.json"
RUNS_DIR = Path(__file__).resolve().parent / "review_eval_runs"

# a noul this close to its threshold gets flagged as borderline
NEAR_MARGIN = 0.1


def load_cases(only: str | None) -> list[dict]:
    """Return cases as {id, source, problem_statement, messages, should_fail}."""
    cases = []
    if only != "cases":
        with open(SCENARIOS_PATH) as f:
            for s in json.load(f)["scenarios"]:
                cases.append(
                    {
                        "id": s["id"],
                        "source": "scenario",
                        "problem_statement": s["problem_statement"],
                        "messages": s["messages"],
                        "should_fail": [],
                    }
                )
    if only != "scenarios":
        with open(CASES_PATH) as f:
            for c in json.load(f)["cases"]:
                cases.append(
                    {
                        "id": c["id"],
                        "source": "case",
                        "problem_statement": c.get("problem_statement", ""),
                        "messages": c["messages"],
                        "should_fail": c.get("should_fail", []),
                    }
                )

    questions = current_app.config["SCENARIO_REVIEW"]["questions"]
    for c in cases:
        unknown = set(c["should_fail"]) - questions.keys()
        if unknown:
            raise ValueError(f"{c['id']}: unknown questions {sorted(unknown)}")

    return cases


def print_case(case: dict, nouls: dict[str, list[float]]) -> bool:
    """Print one case's results. Returns True if it matched expectations."""
    questions = current_app.config["SCENARIO_REVIEW"]["questions"]
    lines = []
    case_ok = True
    case_rejected = False
    for q, details in questions.items():
        expected_fail = q in case["should_fail"]
        if q not in nouls:
            # not sent to Jev for this case (e.g. no problem statement), so it
            # can't fail; expecting it to is a mistake in the case
            if expected_fail:
                case_ok = False
            lines.append(
                f"  {'!!' if expected_fail else '  '} {q:<28} {'not asked':<18}"
                f"{' expected FAIL' if expected_fail else ''}"
            )
            continue

        values = nouls[q]
        fails = sum(is_question_rejected(v, details) for v in values)
        # a question only counts as failed if every repeat failed it,
        # and as passed if every repeat passed it; anything else is mixed
        if fails == len(values):
            outcome = "FAIL"
        elif fails == 0:
            outcome = "pass"
        else:
            outcome = f"MIXED {fails}/{len(values)}"
        if fails:
            case_rejected = True
        mismatch = (fails > 0) != expected_fail or 0 < fails < len(values)
        if mismatch:
            case_ok = False

        mean = sum(values) / len(values)
        noul_str = f"{mean:.2f}"
        if len(values) > 1:
            noul_str += f" ({min(values):.2f}-{max(values):.2f})"
        near = any(abs(v - details["threshold"]) < NEAR_MARGIN for v in values)
        lines.append(
            f"  {'!!' if mismatch else '  '} {q:<28} {noul_str:<18}"
            f" reject {details['reject_if']} {details['threshold']:.2f}"
            f"  {outcome:<9}"
            f"{' expected FAIL' if expected_fail else ''}"
            f"{' (near threshold)' if near else ''}"
        )

    verdict = "REJECTED" if case_rejected else "ACCEPTED"
    expected = "REJECTED" if case["should_fail"] else "ACCEPTED"
    status = "ok" if case_ok else "MISMATCH"
    print(
        f"\n{case['id']} [{case['source']}]  {verdict}"
        f" (expected {expected})  {status}"
    )
    print("\n".join(lines))
    return case_ok


def print_summary(cases: list[dict], all_nouls: dict[str, dict]) -> None:
    """For each question, show how well its threshold separates the cases.

    For a reject-above question, a clean threshold sits between the highest
    noul of cases that should pass and the lowest noul of cases that should
    fail (the other way round for reject-below).
    """
    questions = current_app.config["SCENARIO_REVIEW"]["questions"]
    print("\n" + "=" * 78)
    print("Per question: noul range of cases that should pass / should fail it")
    print("=" * 78)
    for q, details in questions.items():
        should_pass = [
            v for c in cases if q not in c["should_fail"]
            for v in all_nouls[c["id"]].get(q, [])
        ]
        should_fail = [
            v for c in cases if q in c["should_fail"]
            for v in all_nouls[c["id"]].get(q, [])
        ]
        wrongly_failed = sum(is_question_rejected(v, details) for v in should_pass)
        wrongly_passed = sum(
            not is_question_rejected(v, details) for v in should_fail
        )

        def rng(values):
            return f"{min(values):.2f}-{max(values):.2f}" if values else "none"

        print(
            f"{q:<28} reject {details['reject_if']:<5} {details['threshold']:.2f}"
            f"  pass-cases {rng(should_pass):<10} fail-cases {rng(should_fail):<10}"
            f"  wrongly failed {wrongly_failed}/{len(should_pass)},"
            f" wrongly passed {wrongly_passed}/{len(should_fail)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--only", choices=["scenarios", "cases"])
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        cases = load_cases(args.only)
        questions = current_app.config["SCENARIO_REVIEW"]["questions"]

        run_dir = RUNS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir.mkdir(parents=True)
        # keep a copy of the thresholds/questions this run was judged against
        with open(run_dir / "scenario_review.json", "w") as f:
            json.dump(current_app.config["SCENARIO_REVIEW"], f, indent=2)

        all_nouls = {}
        mismatches = []
        total_cost = 0.0
        with (
            open(run_dir / "responses.jsonl", "w") as responses_f,
            open(run_dir / "results.csv", "w", newline="") as csv_f,
        ):
            writer = csv.writer(csv_f)
            writer.writerow(
                [
                    "case_id", "source", "repeat", "question", "noul",
                    "threshold", "reject_if", "rejected", "expected_reject",
                ]
            )
            for case in cases:
                state = build_jev_state(case["problem_statement"], case["messages"])
                # same question set jev_review sends for this problem statement
                jev_questions = build_jev_questions(
                    bool(case["problem_statement"])
                )
                nouls = {q: [] for q in jev_questions}
                for repeat in range(args.repeats):
                    response = jev.fetch_answers(state, jev_questions)
                    responses_f.write(
                        json.dumps(
                            {"case_id": case["id"], "repeat": repeat,
                             "state": state, "response": response}
                        ) + "\n"
                    )
                    if not response or not response.get("answers"):
                        raise SystemExit(
                            f"Jev call failed for {case['id']}, stopping."
                            f" Partial results are in {run_dir}"
                        )
                    total_cost += response.get("usage", {}).get("cost", 0) or 0

                    for q in jev_questions:
                        details = questions[q]
                        noul = response["answers"][q]["noul"]
                        nouls[q].append(noul)
                        writer.writerow(
                            [
                                case["id"], case["source"], repeat, q, noul,
                                details["threshold"], details["reject_if"],
                                is_question_rejected(noul, details),
                                q in case["should_fail"],
                            ]
                        )

                all_nouls[case["id"]] = nouls
                if not print_case(case, nouls):
                    mismatches.append(case["id"])

        print_summary(cases, all_nouls)
        print(
            f"\n{len(cases) - len(mismatches)}/{len(cases)} cases matched"
            f" expectations. Cost ${total_cost:.6f}. Saved to {run_dir}"
        )
        if mismatches:
            print("Mismatches: " + ", ".join(mismatches))


if __name__ == "__main__":
    main()
