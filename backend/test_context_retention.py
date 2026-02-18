#!/usr/bin/env python3
"""
Test script for context retention improvements.
Tests the exact "cacaodoppen" conversation that was failing.
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
TEST_NAME = "Cacaodoppen Context Retention Test"

# Test conversation - the exact failing scenario
TEST_CONVERSATION = [
    {
        "message": "Ik heb een vraag over cacaodoppen",
        "expected_keywords": ["cacaodoppen", "cacao", "schil"],
        "should_not_contain": ["welk product", "wat bedoel je"],
    },
    {
        "message": "Waar kan ik dit voor gebruiken?",
        "expected_keywords": ["cacaodoppen", "tuin", "mulch"],
        "should_not_contain": ["welk product", "over welk product"],
    },
    {
        "message": "Ik heb honden. Deze lopen los in de tuin. Heb je in dit geval een alternatief voor mij?",
        "expected_keywords": ["cacaodoppen", "hond", "alternatief"],
        "should_not_contain": ["welk product", "over welk product", "wat bedoel je"],
        "critical": True,  # This is where it failed before
    },
    {
        "message": "cacaodoppen, dat had ik net gezegd",
        "expected_keywords": ["cacaodoppen"],
        "should_not_contain": ["geen informatie", "weet ik niet", "geen specifieke"],
        "critical": True,  # This is where it claimed ignorance
    },
]

# ANSI color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_success(text):
    """Print success message."""
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")

def print_error(text):
    """Print error message."""
    print(f"{Colors.RED}[ERROR] {text}{Colors.END}")

def print_warning(text):
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.END}")

def print_info(text):
    """Print info message."""
    print(f"{Colors.BLUE}[INFO] {text}{Colors.END}")

def create_session():
    """Create a new chat session."""
    try:
        response = requests.post(f"{BASE_URL}/api/session", timeout=5)
        if response.status_code == 200:
            session_id = response.json()["session_id"]
            print_success(f"Created session: {session_id}")
            return session_id
        else:
            print_error(f"Failed to create session: {response.status_code}")
            return None
    except Exception as e:
        print_error(f"Error creating session: {e}")
        return None

def send_message(session_id, message):
    """Send a message and return the response."""
    try:
        payload = {
            "session_id": session_id,
            "message": message
        }
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            return response.json()
        else:
            print_error(f"Failed to send message: {response.status_code}")
            return None
    except Exception as e:
        print_error(f"Error sending message: {e}")
        return None

def check_response(response_text, expected_keywords, should_not_contain, critical=False):
    """Check if response meets expectations."""
    issues = []
    warnings = []

    # Check for keywords (at least one should be present)
    keyword_found = False
    for keyword in expected_keywords:
        if keyword.lower() in response_text.lower():
            keyword_found = True
            break

    if not keyword_found:
        issues.append(f"Missing expected keywords: {', '.join(expected_keywords)}")

    # Check for phrases that should NOT be present
    for phrase in should_not_contain:
        if phrase.lower() in response_text.lower():
            if critical:
                issues.append(f"[!] CRITICAL: Found forbidden phrase: '{phrase}'")
            else:
                warnings.append(f"Found unexpected phrase: '{phrase}'")

    return issues, warnings

def run_test():
    """Run the full test conversation."""
    print_header(TEST_NAME)
    print_info(f"Testing against: {BASE_URL}")
    print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print_error("Server health check failed!")
            return False
        print_success("Server is running\n")
    except Exception as e:
        print_error(f"Cannot connect to server: {e}")
        print_info("Please start the server with: cd backend && python app.py")
        return False

    # Create session
    session_id = create_session()
    if not session_id:
        return False

    print("\n" + "-"*70 + "\n")

    # Run conversation
    all_passed = True
    for i, turn in enumerate(TEST_CONVERSATION, 1):
        is_critical = turn.get("critical", False)

        print(f"{Colors.BOLD}Turn {i}:{Colors.END}")
        print(f"  User: {turn['message']}")

        # Send message
        response_data = send_message(session_id, turn["message"])

        if not response_data:
            print_error("  Failed to get response")
            all_passed = False
            continue

        response_text = response_data.get("response", "")
        # Encode properly for Windows console
        try:
            display_text = response_text[:100].encode('ascii', 'ignore').decode('ascii')
        except:
            display_text = response_text[:100]
        print(f"  Bot:  {display_text}{'...' if len(response_text) > 100 else ''}")

        # Check response
        issues, warnings = check_response(
            response_text,
            turn["expected_keywords"],
            turn["should_not_contain"],
            is_critical
        )

        # Display results
        if issues:
            for issue in issues:
                print_error(f"  {issue}")
            all_passed = False
        else:
            print_success("  Response looks good!")

        if warnings:
            for warning in warnings:
                print_warning(f"  {warning}")

        print("  " + "-"*68)

        # Small delay between messages
        time.sleep(0.5)

    # Final summary
    print("\n" + "="*70 + "\n")

    if all_passed:
        print_success(f"{Colors.BOLD}ALL TESTS PASSED!{Colors.END}")
        print_info("The chatbot successfully maintained context throughout the conversation.")
        print_info("No 'what product?' questions or false 'I don't know' claims detected.")
    else:
        print_error(f"{Colors.BOLD}SOME TESTS FAILED{Colors.END}")
        print_info("Review the output above for details.")

    print("\n" + "="*70 + "\n")

    # Log file reminder
    print_info("To verify features are working, check the logs:")
    print("  - Query reformulation: Look for 'Query reformulated:'")
    print("  - Entity extraction: Look for 'Extracted conversation entities:'")
    print("  - Enhanced queries: Look for 'Enhanced search query with entities:'")
    print("  - Caching: Look for 'Using cached context for query:'")
    print()
    print(f"  Log file: backend/logs/chat_conversations_{datetime.now().strftime('%Y%m%d')}.log")

    return all_passed

if __name__ == "__main__":
    try:
        success = run_test()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        exit(1)
