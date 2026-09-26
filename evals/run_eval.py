import json
import sys
from pathlib import Path

import requests

EVAL_FILE = Path(__file__).parent / "cases.json"
ENDPOINT = "http://localhost:8000/triage"


def run_eval():
    cases = json.loads(EVAL_FILE.read_text(encoding="utf-8"))

    passed = 0
    failed_cases = []

    for i, case in enumerate(cases, start=1):
        response = requests.post(ENDPOINT, json={"text": case["input"]})

        if response.status_code != 200:
            failed_cases.append({
                "index": i,
                "input": case["input"],
                "expected": case["expected_category"],
                "actual": f"HTTP {response.status_code}",
            })
            continue

        actual = response.json().get("category")
        expected = case["expected_category"]

        if actual == expected:
            passed += 1
        else:
            failed_cases.append({
                "index": i,
                "input": case["input"],
                "expected": expected,
                "actual": actual,
            })

    total = len(cases)
    print(f"\nResult: {passed}/{total} matched ({passed / total * 100:.0f}%)\n")

    if failed_cases:
        print("Failed cases:")
        for fc in failed_cases:
            print(f"  #{fc['index']}: expected '{fc['expected']}', got '{fc['actual']}' — input: {fc['input'][:60]}")
    else:
        print("All cases passed.")


if __name__ == "__main__":
    run_eval()