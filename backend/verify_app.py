import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_homepage():
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            print("[PASS] Homepage loaded (200 OK)")
            if "GroundCoverChatbot" in response.text or "Chat" in response.text:
                 print("[PASS] Homepage content verified")
            else:
                 print("[WARN] Homepage content might be missing expected text")
        else:
            print(f"[FAIL] Homepage returned {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Connection error: {e}")
        sys.exit(1)

def test_shipping_api():
    try:
        data = {"message": "Status for order 123"}
        response = requests.post(f"{BASE_URL}/api/chat", json=data)
        if response.status_code == 200:
            json_resp = response.json()
            if "response" in json_resp:
                print(f"[PASS] Shipping API response: {json_resp['response']}")
            else:
                print(f"[FAIL] Invalid JSON response: {json_resp}")
        else:
            print(f"[FAIL] API returned {response.status_code}")
    except Exception as e:
        print(f"[FAIL] API Connection error: {e}")

def test_dutch_fallback():
    try:
        data = {"message": "Wat is het retourbeleid?"}
        response = requests.post(f"{BASE_URL}/api/chat", json=data)
        if response.status_code == 200:
            json_resp = response.json()
            resp_text = json_resp.get('response', '')
            print(f"[PASS] Dutch Response: {resp_text[:100]}...")
            if "retour" in resp_text.lower() or "bedrijf" in resp_text.lower():
                 print("[PASS] Language detected as Dutch")
            else:
                 print("[WARN] Response might not be in Dutch")
        else:
            print(f"[FAIL] API returned {response.status_code}")
    except Exception as e:
        print(f"[FAIL] API Connection error: {e}")

def test_english_fallback():
    try:
        data = {"message": "What is the return policy?"}
        response = requests.post(f"{BASE_URL}/api/chat", json=data)
        if response.status_code == 200:
            json_resp = response.json()
            resp_text = json_resp.get('response', '')
            print(f"[PASS] English Response: {resp_text[:100]}...")
            if "return" in resp_text.lower() or "policy" in resp_text.lower():
                 print("[PASS] Language detected as English")
            else:
                 print("[WARN] Response might not be in English")
        else:
            print(f"[FAIL] API returned {response.status_code}")
    except Exception as e:
        print(f"[FAIL] API Connection error: {e}")

if __name__ == "__main__":
    print("Starting Verification...")
    test_homepage()
    test_shipping_api()
    test_dutch_fallback()
    test_english_fallback()
    print("Verification Complete.")
