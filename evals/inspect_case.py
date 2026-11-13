"""
evals/inspect_case.py

Print the full transcript of one case (what the caller said, which tools
Zaara called, what she replied, how many words) from the latest results file.

    python -m evals.inspect_case x_double_booking_same_time
"""

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).parent / "results"


def find_latest(case_id):
    for file in sorted(RESULTS.glob("baseline_*.json"), reverse=True):
        data = json.loads(file.read_text(encoding="utf-8"))
        for row in data:
            if row["id"] == case_id:
                return file.name, row
    return None, None


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m evals.inspect_case <case_id>")
        return

    name, row = find_latest(sys.argv[1])
    if not row:
        print(f"No results found for '{sys.argv[1]}'.")
        return

    print(f"From {name}")
    print(f"passed={row['passed']}  failed_checks={row['failed_checks']}\n")

    if row.get("error"):
        print("ERROR:", row["error"])

    result = row.get("result")
    if not result:
        return

    for turn in result["turns"]:
        print(f"USER : {turn['user']}")
        for call in turn["tool_calls"]:
            print(f"  TOOL {call['name']} {call['args']}")
            print(f"       -> {call['result']}")
        reply = turn["reply"] or ""
        print(f"ZAARA: {reply}   [{len(reply.split())} words]\n")


if __name__ == "__main__":
    main()