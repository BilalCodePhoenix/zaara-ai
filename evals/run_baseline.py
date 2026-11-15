"""
evals/run_baseline.py

Runs golden cases through Zaara and scores each one with deterministic
checks (no LLM judge yet). Saves a JSON report in evals/results/.

From the project root:
    python -m evals.run_baseline                    # all cases
    python -m evals.run_baseline extra              # a whole category
    python -m evals.run_baseline happy_toothache    # one or more case ids
    python -m evals.run_baseline --force            # ignore the Sunday guard
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from evals.agent_runner import run_conversation, reset_db, run_tool
from evals.golden_dataset import CASES, resolve, FIND, CHECK, SLOTS, BOOK
from evals.golden_dataset_extra import EXTRA_CASES

ALL_CASES = CASES + EXTRA_CASES
RESULTS_DIR = Path(__file__).parent / "results"

CLAIM_PHRASES = ["book ho gayi", "book ho gaya", "ho gaya ji"]
MASCULINE = [
    "karta hu", "karta hoon", "karunga", "sakta hu", "sakta hoon",
    "chahunga", "bataunga", "dunga",
]
MAX_WORDS = 40  # prompt says 25 (35 in two states); small slack


def norm(value):
    return str(value).strip().lower()


def as_list(value):
    return value if isinstance(value, list) else [value]


def is_subsequence(expected, actual):
    it = iter(actual)
    return all(item in it for item in expected)


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def evaluate(case, result):
    """Return {check_name: True/False} for one finished conversation."""

    calls = result["all_tool_calls"]
    names = [c["name"] for c in calls]
    replies = [t["reply"] or "" for t in result["turns"]]
    all_text = " ".join(replies).lower()

    booked = [
        c for c in calls
        if c["name"] == BOOK and c["result"].get("success") is True
    ]
    find_ok = [
        c for c in calls
        if c["name"] == FIND and c["result"].get("success") is True
    ]
    recommended_ids = {c["result"]["doctor"]["id"] for c in find_ok}
    id_calls = [c for c in calls if c["name"] in (CHECK, SLOTS)]

    checks = {}

    # ---------------- tool calling ----------------
    if "expected_tools" in case:
        checks["right_tools_in_order"] = is_subsequence(
            case["expected_tools"], names
        )

    if "forbidden_tools" in case:
        checks["no_forbidden_tools"] = not (
            set(case["forbidden_tools"]) & set(names)
        )

    if "expected_args" in case:
        ok = True
        for tool, wanted in case["expected_args"].items():
            ok = ok and any(
                c["name"] == tool
                and all(
                    norm(c["args"].get(k)) == norm(v)
                    for k, v in wanted.items()
                )
                for c in calls
            )
        checks["right_tool_args"] = ok

    if "expected_specialization" in case:
        checks["right_doctor_type"] = any(
            c["result"]["doctor"]["specialization"]
            == case["expected_specialization"]
            for c in find_ok
        )

    # doctor_id must come from find_relevant_doctor, never guessed
    if id_calls:
        checks["doctor_id_grounded"] = all(
            to_int(c["args"].get("doctor_id")) in recommended_ids
            for c in id_calls
        )

    # one doctor for every availability / slot lookup
    if case.get("same_doctor_throughout"):
        ids = {to_int(c["args"].get("doctor_id")) for c in id_calls}
        checks["same_doctor_throughout"] = len(ids) == 1

    # last availability lookup uses the doctor from the LAST doctor search
    if case.get("uses_latest_doctor"):
        last_check = [c for c in calls if c["name"] == CHECK][-1:]
        checks["uses_latest_doctor"] = bool(
            last_check and find_ok
            and to_int(last_check[0]["args"].get("doctor_id"))
            == find_ok[-1]["result"]["doctor"]["id"]
        )

    # a booking must be with a doctor Zaara actually recommended
    if booked:
        checks["booking_doctor_was_recommended"] = all(
            c["result"].get("doctor_id") in recommended_ids for c in booked
        )

    # ---------------- task outcome ----------------
    if "must_book" in case:
        checks["booking_outcome_correct"] = (
            bool(booked) if case["must_book"] else not booked
        )

    if case.get("no_overlapping_bookings"):
        slots = [
            (
                norm(c["args"].get("appointment_date")),
                norm(c["args"].get("appointment_time")),
            )
            for c in booked
        ]
        checks["no_overlapping_bookings"] = len(slots) == len(set(slots))

    if "booked_specialization" in case:
        checks["booked_right_doctor_type"] = any(
            c["result"].get("specialization") == case["booked_specialization"]
            for c in booked
        )

    if "booked_args_not" in case:
        checks["not_wrong_slot"] = not any(
            norm(c["args"].get(k)) in {norm(x) for x in as_list(v)}
            for c in booked
            for k, v in case["booked_args_not"].items()
        )

    # ---------------- hallucination ----------------
    claimed = any(p in all_text for p in CLAIM_PHRASES)
    checks["no_false_booking_claim"] = not (claimed and not booked)

    # ---------------- guardrail wording ----------------
    if "reply_must_contain_any" in case:
        checks["guardrail_says_right_thing"] = any(
            p in all_text for p in case["reply_must_contain_any"]
        )
    if "reply_must_not_contain" in case:
        checks["guardrail_avoids_bad_content"] = not any(
            p in all_text for p in case["reply_must_not_contain"]
        )

    # ---------------- voice rules ----------------
    def reply_ok(r):
        low = r.lower()
        return (
            len(r.split()) <= MAX_WORDS
            and not any(ch in r for ch in "*#`")
            and not any(m in low for m in MASCULINE)
        )

    checks["voice_format_ok"] = all(reply_ok(r) for r in replies)

    return checks


def run_case(case, attempts=3):
    case = resolve(case)

    for attempt in range(1, attempts + 1):
        try:
            reset_db()

            for seed in case.get("seed", []):
                res = run_tool(BOOK, dict(seed))
                if not res.get("success"):
                    raise RuntimeError(f"Seed booking failed: {res}")

            return run_conversation(case["turns"], reset=False)

        except Exception as exc:
            print(f"   attempt {attempt} failed: {exc!r}")
            if attempt == attempts:
                raise
            time.sleep(5)


def main():
    force = "--force" in sys.argv[1:]
    wanted = {a for a in sys.argv[1:] if a != "--force"}

    # Many cases say "kal" (tomorrow) or "parso" (day after). The clinic is
    # closed on Sunday, so on a Friday or Saturday those cases would fail
    # for the wrong reason. Run on Sunday-Thursday, or pass --force.
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if not force and any(
        (today + timedelta(days=d)).weekday() == 6 for d in (1, 2)
    ):
        print(
            "Stopping: tomorrow or the day after is a Sunday, and the clinic "
            "is closed on Sundays, so 'kal'/'parso' cases would fail for the "
            "wrong reason. Run this Sunday to Thursday, or add --force."
        )
        return
    cases = [
        c for c in ALL_CASES
        if not wanted or c["id"] in wanted or c["category"] in wanted
    ]

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"baseline_{datetime.now():%Y%m%d_%H%M}.json"

    report = []
    check_totals = {}

    print(f"Running {len(cases)} cases...\n")

    for case in cases:
        print(f"-> {case['id']}")
        try:
            result = run_case(case)
            checks = evaluate(resolve(case), result)
            error = None
        except Exception as exc:
            result, checks, error = None, {"ran_without_error": False}, repr(exc)

        failed = [k for k, v in checks.items() if not v]
        status = "PASS" if not failed else "FAIL"
        print(f"   {status}" + (f"  failed: {failed}" if failed else ""))

        for name, ok in checks.items():
            total = check_totals.setdefault(name, [0, 0])
            total[0] += 1 if ok else 0
            total[1] += 1

        report.append(
            {
                "id": case["id"],
                "category": case["category"],
                "passed": not failed,
                "failed_checks": failed,
                "checks": checks,
                "error": error,
                "result": result,
            }
        )
        out.write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )

    # ---------------- summary ----------------
    passed = sum(1 for r in report if r["passed"])
    print("\n" + "=" * 56)
    print(f"CASES PASSED: {passed}/{len(report)} "
          f"({100 * passed / max(len(report), 1):.0f}%)")
    print("=" * 56)

    print("\nPass rate per check:")
    for name, (ok, total) in sorted(check_totals.items()):
        print(f"  {name:32s} {ok}/{total}  ({100 * ok / total:.0f}%)")

    ran = [r["result"] for r in report if r["result"]]
    if ran:
        turns = [t for r in ran for t in r["turns"]]
        print("\nSpeed and cost:")
        print(f"  avg LLM time per turn   : "
              f"{sum(t['llm_ms'] for t in turns) / len(turns):.0f} ms")
        print(f"  avg input tokens / call : "
              f"{sum(r['total_input_tokens'] for r in ran) / len(ran):.0f}")
        print(f"  avg output tokens / call: "
              f"{sum(r['total_output_tokens'] for r in ran) / len(ran):.0f}")

    print(f"\nFull report saved to {out}")


if __name__ == "__main__":
    main()