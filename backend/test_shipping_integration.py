"""
Integration tests for shipping API features (Features 31-34).

Tests cover:
- Order detection
- Confirmation flow (ja/nee)
- API responses (mock mode)
- State timeout
- Health check integration
"""
import requests
import json
import time
from datetime import datetime


BASE_URL = "http://localhost:5000"


def colored(text, color):
    """Simple colored output for terminal."""
    colors = {
        'green': '\033[92m',
        'red': '\033[91m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'end': '\033[0m'
    }
    return f"{colors.get(color, '')}{text}{colors['end']}"


def test_health_endpoint():
    """Test 1: Health endpoint includes shipping status."""
    print("\n" + colored("TEST 1: Health Endpoint", "blue"))
    print("-" * 50)

    response = requests.get(f"{BASE_URL}/health")
    data = response.json()

    assert "shipping" in data["dependencies"], "Shipping not in health check"
    shipping_status = data["dependencies"]["shipping"]

    print(f"Status: {shipping_status.get('status')}")
    print(f"Message: {shipping_status.get('message')}")

    assert shipping_status["status"] in ["mock_mode", "configured"], \
        f"Unexpected shipping status: {shipping_status['status']}"

    print(colored("[PASS] Health endpoint includes shipping", "green"))
    return True


def test_order_detection():
    """Test 2: Order number detection triggers confirmation."""
    print("\n" + colored("TEST 2: Order Detection", "blue"))
    print("-" * 50)

    # Create session
    session_resp = requests.post(f"{BASE_URL}/api/session")
    session_id = session_resp.json()["session_id"]

    # Test various order formats
    test_cases = [
        "Where is my order 12345?",
        "Waar is bestelling #98765?",
        "Order 54321 status?",
    ]

    for test_msg in test_cases:
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={"session_id": session_id, "message": test_msg}
        )
        data = response.json()
        response_text = data["response"]

        print(f"\nInput: {test_msg}")
        print(f"Response: {response_text}")

        assert "Wil je de status opvragen" in response_text, \
            f"No confirmation prompt for: {test_msg}"
        assert "#" in response_text, "Order number not in confirmation"

    print(colored("\n[PASS]: Order detection works for all formats", "green"))
    return True


def test_confirmation_accept():
    """Test 3: User confirms with 'ja' - shipping status fetched."""
    print("\n" + colored("TEST 3: Confirmation - Accept (ja)", "blue"))
    print("-" * 50)

    # Create session
    session_resp = requests.post(f"{BASE_URL}/api/session")
    session_id = session_resp.json()["session_id"]

    # Step 1: Trigger order detection
    response1 = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": "Where is order 99999?"}
    )
    data1 = response1.json()
    print(f"Bot: {data1['response']}")

    # Step 2: Confirm with "ja"
    response2 = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": "ja"}
    )
    data2 = response2.json()
    response_text = data2["response"]
    print(f"Bot: {response_text}")

    # Should show shipping status
    assert any(word in response_text for word in ["onderweg", "afgeleverd", "Status"]), \
        "No shipping status in response"
    assert "#99999" in response_text, "Order number not in status response"

    # Test other confirmation words
    for confirm_word in ["yes", "correct", "klopt"]:
        session_resp = requests.post(f"{BASE_URL}/api/session")
        sid = session_resp.json()["session_id"]

        requests.post(f"{BASE_URL}/api/chat",
                     json={"session_id": sid, "message": "order 77777"})
        response = requests.post(f"{BASE_URL}/api/chat",
                                json={"session_id": sid, "message": confirm_word})

        assert "onderweg" in response.json()["response"] or "Status" in response.json()["response"], \
            f"'{confirm_word}' not recognized as confirmation"

    print(colored("\n[PASS]: Confirmation (ja/yes/correct) works", "green"))
    return True


def test_confirmation_decline():
    """Test 4: User declines with 'nee' - asks for correct number."""
    print("\n" + colored("TEST 4: Confirmation - Decline (nee)", "blue"))
    print("-" * 50)

    # Create session
    session_resp = requests.post(f"{BASE_URL}/api/session")
    session_id = session_resp.json()["session_id"]

    # Step 1: Trigger order detection
    response1 = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": "Order 88888?"}
    )
    data1 = response1.json()
    print(f"Bot: {data1['response']}")

    # Step 2: Decline with "nee"
    response2 = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": "nee"}
    )
    data2 = response2.json()
    response_text = data2["response"]
    print(f"Bot: {response_text}")

    assert "correcte bestelnummer" in response_text.lower() or "correct" in response_text.lower(), \
        "No prompt for correct order number"

    print(colored("\n[PASS]: Decline (nee) asks for correct number", "green"))
    return True


def test_mock_mode_responses():
    """Test 5: Mock mode returns realistic test data."""
    print("\n" + colored("TEST 5: Mock Mode Responses", "blue"))
    print("-" * 50)

    # Create session
    session_resp = requests.post(f"{BASE_URL}/api/session")
    session_id = session_resp.json()["session_id"]

    # Trigger and confirm
    requests.post(f"{BASE_URL}/api/chat",
                 json={"session_id": session_id, "message": "order 12345"})
    response = requests.post(f"{BASE_URL}/api/chat",
                            json={"session_id": session_id, "message": "ja"})

    data = response.json()
    response_text = data["response"]

    print(f"Mock response: {response_text}")

    # Check for mock data elements
    assert "onderweg" in response_text or "in transit" in response_text.lower(), \
        "No transit status in mock response"

    # Mock should include location and delivery date
    has_location = "locatie" in response_text.lower() or "location" in response_text.lower()
    has_date = "levering" in response_text.lower() or "delivery" in response_text.lower()

    assert has_location and has_date, "Mock response missing location or delivery date"

    print(colored("\n[PASS]: Mock mode returns realistic data", "green"))
    return True


def test_state_persistence():
    """Test 6: Confirmation state persists across requests."""
    print("\n" + colored("TEST 6: State Persistence", "blue"))
    print("-" * 50)

    # Create session
    session_resp = requests.post(f"{BASE_URL}/api/session")
    session_id = session_resp.json()["session_id"]

    # Trigger confirmation
    response1 = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": "order 11111"}
    )
    print(f"Request 1: {response1.json()['response']}")

    # Wait a moment (simulate user thinking)
    time.sleep(2)

    # Confirm in separate request
    response2 = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": "ja"}
    )
    response_text = response2.json()["response"]
    print(f"Request 2: {response_text}")

    # Should show shipping status, not treat "ja" as a normal message
    assert "onderweg" in response_text or "Status" in response_text, \
        "State not persisted - 'ja' treated as normal message"

    print(colored("\n[PASS]: State persists across HTTP requests", "green"))
    return True


def test_no_false_confirmations():
    """Test 7: "ja" without pending confirmation doesn't trigger lookup."""
    print("\n" + colored("TEST 7: No False Confirmations", "blue"))
    print("-" * 50)

    # Create session
    session_resp = requests.post(f"{BASE_URL}/api/session")
    session_id = session_resp.json()["session_id"]

    # Say "ja" without any pending confirmation
    response = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": "ja"}
    )
    response_text = response.json()["response"]

    print(f"Response to standalone 'ja': {response_text[:100]}...")

    # Should NOT show shipping status
    assert "onderweg" not in response_text and "tracking" not in response_text.lower(), \
        "'ja' without confirmation triggered shipping lookup"

    print(colored("\n[PASS]: No false confirmations", "green"))
    return True


def run_all_tests():
    """Run all integration tests."""
    print(colored("\n" + "=" * 50, "blue"))
    print(colored("SHIPPING API INTEGRATION TESTS", "blue"))
    print(colored("Features 31-34", "blue"))
    print(colored("=" * 50 + "\n", "blue"))

    tests = [
        test_health_endpoint,
        test_order_detection,
        test_confirmation_accept,
        test_confirmation_decline,
        test_mock_mode_responses,
        test_state_persistence,
        test_no_false_confirmations,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            failed += 1
            print(colored(f"[FAIL]: {e}", "red"))
        except Exception as e:
            failed += 1
            print(colored(f"[ERROR]: {e}", "red"))

    # Summary
    print("\n" + colored("=" * 50, "blue"))
    print(colored(f"RESULTS: {passed} passed, {failed} failed", "yellow"))
    print(colored("=" * 50, "blue"))

    if failed == 0:
        print(colored("\nSUCCESS: All tests passed!", "green"))
        return 0
    else:
        print(colored(f"\nWARNING: {failed} test(s) failed", "red"))
        return 1


if __name__ == "__main__":
    try:
        exit_code = run_all_tests()
        exit(exit_code)
    except KeyboardInterrupt:
        print(colored("\n\nTests interrupted by user", "yellow"))
        exit(1)
    except requests.exceptions.ConnectionError:
        print(colored("\n[ERROR]: Cannot connect to Flask server", "red"))
        print(colored("Make sure Flask is running on http://localhost:5000", "yellow"))
        exit(1)
