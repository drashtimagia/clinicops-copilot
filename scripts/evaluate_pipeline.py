"""
ClinicOps Copilot — Full Real-Data Evaluation Pipeline
Runs all 10 incidents from data/incidents/reports.json through the core pipeline
and compares results against expected_outcomes.json.
"""
import json
import os
import sys

# Add backend/ to path so ai_pipeline imports work
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')
sys.path.insert(0, BACKEND_DIR)

from ai_pipeline.api import _initialize_services, process_incident

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INCIDENTS_FILE = os.path.join(DATA_DIR, "incidents", "reports.json")
EXPECTED_FILE = os.path.join(DATA_DIR, "expected_outcomes.json")


def run_evaluation():
    print("=" * 60)
    print("  ClinicOps Copilot — Full Pipeline Evaluation")
    print("=" * 60)

    # Load data
    with open(INCIDENTS_FILE, "r") as f:
        incidents = json.load(f)
    with open(EXPECTED_FILE, "r") as f:
        expected = json.load(f)

    print(f"\nRunning {len(incidents)} incidents against expected outcomes...\n")

    results = []
    passed = 0
    failed = 0

    for incident in incidents:
        inc_id = incident["id"]
        payload = {
            "incident_id": inc_id,
            "device_id": incident.get("device", ""),
            "description": incident.get("description", ""),
            "reporter": incident.get("reporter", "Unknown")
        }

        try:
            result = process_incident(payload)
            exp = expected.get(inc_id, {})

            expected_escalate = exp.get("expected_escalate")
            actual_escalate = result.get("escalate", False)
            escalate_match = (expected_escalate == actual_escalate)

            technician_required = result.get("technician_required", False)
            resolution_step_count = len(result.get("resolution_steps", []))
            diagnosis = result.get("diagnosis", "N/A")
            confidence = result.get("confidence", 0.0)

            status = "PASS ✅" if escalate_match else "FAIL ❌"
            if escalate_match:
                passed += 1
            else:
                failed += 1

            print(f"[{status}] {inc_id}")
            print(f"  Device     : {incident.get('device', 'N/A')}")
            print(f"  Diagnosis  : {diagnosis}")
            print(f"  Escalate   : actual={actual_escalate}, expected={expected_escalate}")
            print(f"  Technician : {technician_required}")
            print(f"  Resolution : {resolution_step_count} steps")
            print(f"  Confidence : {confidence:.2f}")
            if not escalate_match:
                print(f"  Expected   : {exp.get('expected_action_summary', 'N/A')}")
            print()

            results.append({
                "incident_id": inc_id,
                "status": "pass" if escalate_match else "fail",
                "escalate_match": escalate_match,
                "actual_escalate": actual_escalate,
                "expected_escalate": expected_escalate,
                "technician_required": technician_required,
                "resolution_steps": resolution_step_count,
                "confidence": confidence
            })

        except Exception as e:
            failed += 1
            print(f"[ERROR] {inc_id}: {e}\n")
            results.append({"incident_id": inc_id, "status": "error", "error": str(e)})

    print("=" * 60)
    print(f"  RESULTS: {passed}/{len(incidents)} passed | {failed} failed")
    accuracy = (passed / len(incidents)) * 100 if incidents else 0
    print(f"  ESCALATION ACCURACY: {accuracy:.1f}%")
    print("=" * 60)
    return results


if __name__ == "__main__":
    _initialize_services()
    run_evaluation()
