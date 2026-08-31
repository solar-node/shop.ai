"""Run the benchmark scenarios and print simple completion metrics."""

import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.agents.orchestrator import Orchestrator


def load_benchmark():
    with open(os.path.join(os.path.dirname(__file__), "benchmark.json")) as file:
        return json.load(file)


def score_scenario(scenario: dict, state: dict) -> bool:
    expected = scenario["expect"]
    status = state.get("status")
    if expected == "candidates_found":
        return status != "FAILED"
    if expected == "auto_purchase_or_pending":
        return status in ("PAYMENT_PENDING", "AWAITING_APPROVAL", "AWAITING_PAYMENT")
    if expected == "user_confirmation_requested":
        return status == "AWAITING_APPROVAL"
    if expected in ("budget_respected", "offer_applied", "replan_on_failure"):
        return status != "FAILED"
    return status != "FAILED"


def run_benchmark():
    results, latencies = [], []

    for scenario in load_benchmark():
        session_id = f"eval_{uuid.uuid4().hex[:8]}"
        start = time.time()
        try:
            state = Orchestrator(session_id, scenario["goal"]).run()
            success, error = score_scenario(scenario, state), None
        except Exception as exc:
            state, success, error = {}, False, str(exc)

        latency = time.time() - start
        latencies.append(latency)
        results.append({
            "id": scenario["id"], "goal": scenario["goal"], "success": success,
            "status": state.get("status"), "latency_s": round(latency, 2), "error": error,
        })
        print(f"[{scenario['id']}] {'PASS' if success else 'FAIL'} "
              f"status={state.get('status')} ({latency:.1f}s)" +
              (f" ERROR={error}" if error else ""))

    completion = sum(r["success"] for r in results) / len(results) * 100
    average = sum(latencies) / len(latencies)
    print(f"\nTask completion rate: {completion:.1f}%")
    print(f"Average latency: {average:.2f}s")

    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as file:
        json.dump({"results": results, "completion_rate": completion,
                   "avg_latency_s": average}, file, indent=2)


if __name__ == "__main__":
    run_benchmark()
