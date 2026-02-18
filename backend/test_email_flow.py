"""Test the full chat escalation flow end-to-end."""
import requests
import json

BASE = "http://127.0.0.1:5000"

# Step 1: Create session
s = requests.post(f"{BASE}/api/session")
sid = s.json()["session_id"]
print(f"Session: {sid}")

# Step 2: Ask to speak with someone (triggers human handoff)
r = requests.post(f"{BASE}/api/chat", json={"message": "ik wil graag met iemand praten", "session_id": sid})
print(f"Step 2 (handoff): {r.status_code} - {r.json()}")

# Step 3: Provide name
r = requests.post(f"{BASE}/api/chat", json={"message": "Test User", "session_id": sid})
print(f"Step 3 (name):    {r.status_code} - {r.json()}")

# Step 4: Provide email - THIS is where the error occurred
r = requests.post(f"{BASE}/api/chat", json={"message": "w.schouten@eurostyle.nl", "session_id": sid})
print(f"Step 4 (email):   {r.status_code}")
ct = r.headers.get("Content-Type", "unknown")
print(f"  Content-Type: {ct}")
try:
    data = r.json()
    print(f"  JSON response: {json.dumps(data, indent=2, ensure_ascii=False)}")
except Exception as e:
    print(f"  NOT JSON! Parse error: {e}")
    print(f"  Raw response (first 500 chars):")
    print(f"  {r.text[:500]}")
