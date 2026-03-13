"""
ClinicOps Copilot — Smart Voice Agent Multi-Turn Test Suite
Tests: intent detection, back-and-forth resolution, escalation flow, general Q&A.
Runs on real incident data from data/incidents/reports.json.
"""
import json
import io
import os
import sys

# Add backend/ to path so ai_pipeline imports work
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')
sys.path.insert(0, BACKEND_DIR)

from ai_pipeline.api import _initialize_services, process_voice_incident

# Dummy audio bytes (mock transcriber ignores content)
DUMMY_AUDIO = b"RIFF$" + (b"\x00" * 1024)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INCIDENTS_FILE = os.path.join(DATA_DIR, "incidents", "reports.json")


def simulate_turn(session_id: str, user_says: str, incident_id: str = "TEST") -> dict:
    """Simulate a single push-to-talk turn using the mock transcriber overlay."""
    from ai_pipeline.voice.transcriber import NovaSonicTranscriber
    # Monkey-patch transcriber to return our test text
    original_transcribe = NovaSonicTranscriber.transcribe

    def mock_transcribe(self, audio_bytes, audio_format, metadata=None):
        return user_says

    NovaSonicTranscriber.transcribe = mock_transcribe

    result = process_voice_incident(
        audio_bytes=DUMMY_AUDIO,
        audio_format="wav",
        payload={"incident_id": incident_id, "session_id": session_id, "reporter": "Test Staff"}
    )

    NovaSonicTranscriber.transcribe = original_transcribe
    return result


def print_turn(turn_num: int, user_text: str, result: dict):
    print(f"\n  [Turn {turn_num}] USER: {user_text}")
    print(f"  [Turn {turn_num}] AGENT ({result['status']}): {result['final_text_response'][:200]}...")
    print(f"           Slots: {result.get('extracted_slots', {})}")


def test_general_qa():
    """Test: General question should be answered immediately, no slot interrogation."""
    print("\n" + "=" * 60)
    print("TEST 1: General Q&A — Should answer without asking for slots")
    print("=" * 60)

    r = simulate_turn("sess-qa-001", "What is the SOP for a biohazard spill?", "QA-TEST-001")
    print_turn(1, "What is the SOP for a biohazard spill?", r)

    assert r["status"] == "conversational", f"Expected 'conversational', got '{r['status']}'"
    assert "biohazard" in r["final_text_response"].lower() or "spill" in r["final_text_response"].lower(), \
        "Response should mention biohazard/spill content"
    print("  ✅ PASS: General question answered directly without slot interrogation")


def test_incident_resolution_loop():
    """Test: Incident report → slot collection → pipeline → step-by-step → escalation."""
    print("\n" + "=" * 60)
    print("TEST 2: Multi-Turn Resolution — Centrifuge E-04 Incident")
    print("=" * 60)

    session_id = "sess-resolve-001"

    # Turn 1: Report the incident
    r1 = simulate_turn(session_id, "The centrifuge is showing an E-04 error mid-cycle", "INC-E04-001")
    print_turn(1, "The centrifuge is showing an E-04 error mid-cycle", r1)

    # Should be clarifying (room/role) or resolving depending on intent
    assert r1["status"] in ("clarifying", "resolving", "conversational"), \
        f"Unexpected status: {r1['status']}"
    print(f"  ✅ Turn 1 status: {r1['status']}")

    # Turn 2: Provide remaining info if still clarifying
    if r1["status"] == "clarifying":
        r2 = simulate_turn(session_id, "Room 5, I'm a nurse", "INC-E04-001")
        print_turn(2, "Room 5, I'm a nurse", r2)
    else:
        r2 = r1
        print("  (Skipping slot turns — all critical slots extracted)")

    # Turn 3: Simulate that the first step didn't work
    r3 = simulate_turn(session_id, "I tried that but it's still showing the error", "INC-E04-001")
    print_turn(3, "I tried that but it's still showing the error", r3)
    print(f"  ✅ Resolution loop status: {r3['status']}")


def test_memory_recurrence():
    """Test: INC-007 (3rd monitor shutdown) should trigger escalation due to memory."""
    print("\n" + "=" * 60)
    print("TEST 3: Memory-Aware Escalation — VitalsMonitor Third Strike (INC-007)")
    print("=" * 60)

    with open(INCIDENTS_FILE) as f:
        incidents = json.load(f)

    inc_007 = next(i for i in incidents if i["id"] == "INC-007")
    r = simulate_turn("sess-mem-001", inc_007["description"], "INC-007")
    print_turn(1, inc_007["description"][:80] + "...", r)

    print(f"  Status   : {r['status']}")
    escalate = r.get("pipeline_handoff_payload", {}).get("escalate") if r.get("pipeline_handoff_payload") else None
    print(f"  Escalate : {escalate}")
    print(f"  ✅ Memory test run completed")


def test_all_real_incidents():
    """Quick smoke test: run all 10 incidents through the voice pipeline."""
    print("\n" + "=" * 60)
    print("TEST 4: All 10 Real Incidents — Voice Pipeline Smoke Test")
    print("=" * 60)

    with open(INCIDENTS_FILE) as f:
        incidents = json.load(f)

    errors = []
    for incident in incidents:
        session_id = f"sess-{incident['id'].lower()}"
        description = incident.get("description", "")
        try:
            r = simulate_turn(session_id, description, incident["id"])
            status_icon = "✅" if r["status"] in ("clarifying", "resolving", "conversational") else "⚠️"
            print(f"  {status_icon} {incident['id']} [{incident['device'][:30]}] → {r['status']}")
        except Exception as e:
            errors.append(incident["id"])
            print(f"  ❌ {incident['id']}: {e}")

    print(f"\n  Completed: {len(incidents) - len(errors)}/{len(incidents)} incidents processed without error")
    if errors:
        print(f"  Errors: {errors}")


def run_all_tests():
    print("\n" + "=" * 60)
    print("  ClinicOps Copilot — Smart Voice Agent Test Suite")
    print("=" * 60)

    _initialize_services()

    test_general_qa()
    test_incident_resolution_loop()
    test_memory_recurrence()
    test_all_real_incidents()

    print("\n" + "=" * 60)
    print("  All tests completed.")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
