"""Verify StatusWeb shipping API credentials."""
import os
import sys

# Load .env from the same directory as this script
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

STATUSWEB_WSDL = 'https://www.statusweb.nl/StatuswebAPIv4/Service.wso?WSDL'

SW_OK = 1
SW_UNKNOWN_API_KEY = -99
SW_UNKNOWN_TRANSPORT_NUMBER = -150
SW_NO_STATUSES_FOUND = -200


def main():
    api_key = os.getenv('SHIPPING_API_KEY', '')
    api_password = os.getenv('SHIPPING_API_PASSWORD', '')

    if not api_key or not api_password:
        print("ERROR: SHIPPING_API_KEY or SHIPPING_API_PASSWORD not set in .env")
        sys.exit(1)

    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"WSDL:    {STATUSWEB_WSDL}")
    print()

    # Step 1: Load WSDL and create SOAP client
    print("Step 1: Connecting to StatusWeb WSDL...")
    try:
        from zeep import Client as ZeepClient
        client = ZeepClient(wsdl=STATUSWEB_WSDL)
        print("  SOAP client initialized OK")
    except Exception as e:
        print(f"  FAILED to load WSDL: {e}")
        sys.exit(1)

    # Step 2: Authenticate (get session ID)
    print("\nStep 2: Authenticating with GetSessionId...")
    try:
        result = client.service.GetSessionID(
            ApiKey=api_key,
            Wachtwoord=api_password
        )
        error_code = getattr(result, 'Errorcode', None)
        error_string = getattr(result, 'Errorstring', '')
        session_id = getattr(result, 'SessionID', None)

        if error_code == SW_OK:
            print(f"  Authentication successful! Session ID: {session_id}")
        elif error_code == SW_UNKNOWN_API_KEY:
            print(f"  Authentication FAILED: Unknown API key (code {error_code})")
            print(f"  Message: {error_string}")
            sys.exit(1)
        else:
            print(f"  Unexpected response (code {error_code}): {error_string}")
            sys.exit(1)
    except Exception as e:
        print(f"  Authentication request FAILED: {e}")
        sys.exit(1)

    # Step 3: Test a lookup with a dummy tracking number
    print("\nStep 3: Testing lookup with dummy tracking number 99999...")
    try:
        result = client.service.GetStatusVrachtnummer(
            SessionID=session_id,
            Vrachtnummer=float(99999)
        )
        error_code = getattr(result, 'Errorcode', None)
        error_string = getattr(result, 'Errorstring', '')

        if error_code in (SW_UNKNOWN_TRANSPORT_NUMBER, SW_NO_STATUSES_FOUND):
            print(f"  API responds correctly (got expected '{error_string}' for dummy number)")
        elif error_code == SW_OK:
            print(f"  Surprisingly, number 99999 returned a result!")
        else:
            print(f"  Response code {error_code}: {error_string}")

    except Exception as e:
        print(f"  Lookup request failed: {e}")

    # Summary
    print("\n" + "=" * 50)
    print("RESULT: API credentials are valid and working!")
    print("=" * 50)
    print("\nNext steps:")
    print("  1. Add SHIPPING_API_KEY and SHIPPING_API_PASSWORD to Railway variables")
    print("  2. Test with a real tracking number via the chatbot")


if __name__ == '__main__':
    main()
