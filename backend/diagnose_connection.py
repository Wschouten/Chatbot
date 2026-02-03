import requests
import json
import time

url = "http://127.0.0.1:5000/api/chat"
payload = {"message": "Ik heb last van slakken in mijn tuin"}

print(f"Testing connection to {url}...")
try:
    start = time.time()
    response = requests.post(url, json=payload, timeout=60)
    duration = time.time() - start
    
    print(f"Status Code: {response.status_code}")
    print(f"Duration: {duration:.2f}s")
    
    try:
        data = response.json()
        print("Valid JSON received:")
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print("INVALID JSON RECEIVED. Raw Content:")
        print(response.text[:1000]) # Print first 1000 chars

except requests.exceptions.Timeout:
    print("Request TIMED OUT after 60s.")
except requests.exceptions.ConnectionError:
    print("CONNECTION REFUSED. Is the server running?")
except Exception as e:
    print(f"An error occurred: {e}")
