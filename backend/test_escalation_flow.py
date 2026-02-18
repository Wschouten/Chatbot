"""Reproduce the exact flow: ask for human -> name -> email -> check for errors."""
import requests
import json
import time

BASE = "http://127.0.0.1:5000"

# 1. Create session
s = requests.post(f"{BASE}/api/session", json={})
print(f"Session: {s.status_code} {s.text[:200]}")
sid = s.json().get("session_id", "")
print(f"Session ID: {sid}\n")

# 2. Ask to speak to someone (triggers handoff)
r1 = requests.post(f"{BASE}/api/chat", json={"session_id": sid, "message": "ik wil graag met iemand spreken"})
print(f"Step 1 (handoff): {r1.status_code}")
print(f"  Content-Type: {r1.headers.get('content-type')}")
try:
    print(f"  Body: {r1.json()}")
except Exception as e:
    print(f"  RAW BODY: {r1.text[:500]}")
    print(f"  JSON parse error: {e}")
print()

time.sleep(1)

# 3. Give name
r2 = requests.post(f"{BASE}/api/chat", json={"session_id": sid, "message": "Wilco"})
print(f"Step 2 (name): {r2.status_code}")
print(f"  Content-Type: {r2.headers.get('content-type')}")
try:
    print(f"  Body: {r2.json()}")
except Exception as e:
    print(f"  RAW BODY: {r2.text[:500]}")
    print(f"  JSON parse error: {e}")
print()

time.sleep(1)

# 4. Give email (THIS is where the error happens)
r3 = requests.post(f"{BASE}/api/chat", json={"session_id": sid, "message": "w.schouten@eurostyle.nl"})
print(f"Step 3 (email): {r3.status_code}")
print(f"  Content-Type: {r3.headers.get('content-type')}")
try:
    print(f"  Body: {r3.json()}")
except Exception as e:
    print(f"  RAW BODY: {r3.text[:1000]}")
    print(f"  JSON parse error: {e}")
