"""Force the session into awaiting_email state, then submit the email to reproduce the error."""
import requests
import json
import os
import sys

BASE = "http://127.0.0.1:5000"

# 1. Create session
s = requests.post(f"{BASE}/api/session", json={})
sid = s.json().get("session_id", "")
print(f"Session ID: {sid}")

# 2. Force the session into awaiting_email state by writing state directly
state_file = f"/app/backend/sessions/{sid}.json"
state_data = {
    "state": "awaiting_email",
    "name": "Wilco",
    "question": "ik wil met iemand praten",
    "language": "nl",
    "chat_history": [
        {"role": "user", "content": "ik wil met iemand praten"},
        {"role": "assistant", "content": "Natuurlijk! Wat is je naam?"},
        {"role": "user", "content": "Wilco"},
        {"role": "assistant", "content": "Leuk je te ontmoeten! Wat is je e-mailadres?"}
    ]
}
with open(state_file, 'w') as f:
    json.dump(state_data, f)
print(f"Set state to awaiting_email")

# 3. Now submit an email - this should trigger the escalation
print(f"\nSending email: w.schouten@eurostyle.nl")
r = requests.post(f"{BASE}/api/chat", json={"session_id": sid, "message": "w.schouten@eurostyle.nl"})
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}")
print(f"Body length: {len(r.text)}")
if 'application/json' in r.headers.get('content-type', ''):
    print(f"JSON: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
else:
    print(f"RAW BODY (first 2000 chars):")
    print(r.text[:2000])
