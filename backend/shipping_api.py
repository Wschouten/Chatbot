"""Shipping status API module - Van Den Heuvel / StatusWeb SOAP Integration."""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# StatusWeb SOAP WSDL endpoint
STATUSWEB_WSDL = 'https://www.statusweb.nl/StatuswebAPIv4/Service.wso?WSDL'

# StatusWeb error codes
SW_OK = 1
SW_UNKNOWN_API_KEY = -99
SW_UNKNOWN_TRANSPORT_NUMBER = -150
SW_NO_STATUSES_FOUND = -200
SW_NO_ETA = -320
SW_NO_STATUS_URL = -500
SW_SESSION_EXPIRED = -96
SW_INVALID_SESSION = -98


class ShippingAPIClient:
    """Client for Van Den Heuvel shipping API via StatusWeb SOAP."""

    def __init__(self):
        self.api_key = os.getenv('SHIPPING_API_KEY', '')
        self.api_password = os.getenv('SHIPPING_API_PASSWORD', '')
        self.use_mock = not self.api_key  # Auto-enable mock if no key

        # Session management (cached for performance)
        self._session_id: Optional[str] = None
        self._session_expires: Optional[datetime] = None
        self._soap_client = None

        if self.use_mock:
            logger.warning("SHIPPING_API_KEY not set - using mock responses")
        else:
            logger.info("StatusWeb shipping API configured (Van Den Heuvel)")

    def _get_soap_client(self):
        """Lazy-initialize the SOAP client (zeep)."""
        if self._soap_client is None:
            try:
                from zeep import Client as ZeepClient
                self._soap_client = ZeepClient(wsdl=STATUSWEB_WSDL)
                logger.info("StatusWeb SOAP client initialized (WSDL loaded)")
            except Exception as e:
                logger.error("Failed to initialize SOAP client: %s", e)
                raise
        return self._soap_client

    def _get_session_id(self) -> str:
        """
        Get a valid StatusWeb session ID.

        Sessions are valid for 2 hours. We cache with a 1h55m margin
        to avoid using expired tokens.
        """
        now = datetime.now()

        # Return cached session if still valid
        if (self._session_id and self._session_expires
                and now < self._session_expires):
            return self._session_id

        # Request new session
        logger.info("Requesting new StatusWeb session...")
        client = self._get_soap_client()

        try:
            result = client.service.GetSessionID(
                ApiKey=self.api_key,
                Wachtwoord=self.api_password
            )

            # Extract fields directly from zeep response object
            error_code = getattr(result, 'Errorcode', 0)
            session_id = getattr(result, 'SessionID', None)

            if error_code != SW_OK:
                error_msg = getattr(result, 'Errorstring', '')
                logger.error("StatusWeb auth failed (code %s): %s", error_code, error_msg)
                raise ConnectionError(f"StatusWeb authentication failed: {error_msg}")

            self._session_id = str(session_id)
            # Cache with 1h55m margin (sessions valid for 2 hours)
            self._session_expires = now + timedelta(hours=1, minutes=55)

            logger.info("StatusWeb session obtained, expires at %s",
                        self._session_expires.strftime('%H:%M:%S'))
            return self._session_id

        except ConnectionError:
            raise
        except Exception as e:
            logger.error("StatusWeb session request failed: %s", e)
            raise ConnectionError(f"Could not authenticate with StatusWeb: {e}")

    def get_shipment_status(self, tracking_code: str) -> Dict[str, Any]:
        """
        Get shipment status from StatusWeb.

        Args:
            tracking_code: Van Den Heuvel zendingnummer/vrachtnummer

        Returns:
            Dict with keys: success (bool), status (str), details (dict), error (str)
        """
        if self.use_mock:
            return self._mock_response(tracking_code)

        try:
            session_id = self._get_session_id()
            client = self._get_soap_client()

            # Convert to float (StatusWeb expects numeric Vrachtnummer)
            try:
                vrachtnummer = float(tracking_code)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "status": "invalid_number",
                    "details": {},
                    "error": f"'{tracking_code}' is geen geldig zendingnummer"
                }

            # Call GetStatusVrachtnummer
            result = client.service.GetStatusVrachtnummer(
                SessionID=session_id,
                Vrachtnummer=vrachtnummer
            )

            error_code = getattr(result, 'Errorcode', 0)

            if error_code == SW_UNKNOWN_TRANSPORT_NUMBER:
                return {
                    "success": False,
                    "status": "not_found",
                    "details": {},
                    "error": "Zendingnummer niet gevonden"
                }

            if error_code == SW_NO_STATUSES_FOUND:
                return {
                    "success": False,
                    "status": "no_status",
                    "details": {},
                    "error": "Er is nog geen status beschikbaar voor deze zending"
                }

            if error_code in (SW_SESSION_EXPIRED, SW_INVALID_SESSION):
                # Session expired — clear cache and retry once
                logger.warning("StatusWeb session expired, refreshing...")
                self._session_id = None
                self._session_expires = None
                return self.get_shipment_status(tracking_code)

            if error_code != SW_OK:
                error_msg = getattr(result, 'Errorstring', 'Onbekende fout')
                return {
                    "success": False,
                    "status": "error",
                    "details": {},
                    "error": f"StatusWeb fout: {error_msg}"
                }

            # Parse status entries
            statuses = []
            raw_statuses = getattr(result, 'Status', [])
            if raw_statuses:
                # Can be a single object or a list
                if not isinstance(raw_statuses, list):
                    raw_statuses = [raw_statuses]

                for s in raw_statuses:
                    statuses.append({
                        "transport_number": getattr(s, 'Vrachtnummer', tracking_code),
                        "reference": getattr(s, 'Kenmerk', None),
                        "date": getattr(s, 'Datum', ''),
                        "time": getattr(s, 'Tijd', ''),
                        "status_number": getattr(s, 'StatusNummer', 0),
                        "status_description": getattr(s, 'StatusOmschrijving', ''),
                        "note": getattr(s, 'Opmerking', ''),
                    })

            # Use the latest status entry
            latest = statuses[-1] if statuses else {}
            status_desc = latest.get("status_description", "onbekend")

            # Determine simplified status category
            status_lower = status_desc.lower()
            if any(w in status_lower for w in ["afgeleverd", "delivered", "bezorgd"]):
                simplified_status = "delivered"
            elif any(w in status_lower for w in ["onderweg", "transit", "geladen", "vertrokken"]):
                simplified_status = "in_transit"
            elif any(w in status_lower for w in ["depot", "hub", "sorteer"]):
                simplified_status = "at_depot"
            else:
                simplified_status = "in_transit"  # Default for active shipments

            details = {
                "status_description": status_desc,
                "date": latest.get("date", ""),
                "time": latest.get("time", ""),
                "reference": latest.get("reference"),
                "note": latest.get("note", ""),
                "all_statuses": statuses,
            }

            # Try to get ETA (supplementary, non-critical)
            try:
                eta_result = client.service.GetETAVrachtnummer(
                    SessionID=session_id,
                    Vrachtnummer=vrachtnummer
                )
                eta_error = getattr(eta_result, 'Errorcode', 0)
                if eta_error == SW_OK:
                    details["eta_from"] = str(getattr(eta_result, 'ETA_Van', ''))
                    details["eta_until"] = str(getattr(eta_result, 'ETA_Tot', ''))
            except Exception as e:
                logger.debug("ETA lookup skipped: %s", e)

            # Try to get Track & Trace URL (supplementary, non-critical)
            try:
                url_result = client.service.GetStatusweblinkVrachtnummer(
                    SessionID=session_id,
                    Vrachtnummer=vrachtnummer
                )
                url_error = getattr(url_result, 'Errorcode', 0)
                if url_error == SW_OK:
                    details["tracking_url"] = str(getattr(url_result, 'Statusweblink', ''))
            except Exception as e:
                logger.debug("Tracking URL lookup skipped: %s", e)

            return {
                "success": True,
                "status": simplified_status,
                "details": details,
                "error": None
            }

        except ConnectionError as e:
            logger.error("StatusWeb connection error: %s", e)
            return {
                "success": False,
                "status": "error",
                "details": {},
                "error": "Kon geen verbinding maken met de vervoerder"
            }
        except Exception as e:
            logger.error("StatusWeb API error: %s", e)
            return {
                "success": False,
                "status": "error",
                "details": {},
                "error": "Er ging iets mis bij het ophalen van de status"
            }

    def _mock_response(self, tracking_code: str) -> Dict[str, Any]:
        """Mock response for testing without API key."""
        return {
            "success": True,
            "status": "in_transit",
            "details": {
                "status_description": "Onderweg naar afleveradres",
                "tracking_code": tracking_code,
                "date": "2026-02-16",
                "time": "14:30",
                "estimated_delivery": "2026-02-17",
                "location": "Distributiecentrum Utrecht",
                "reference": None,
                "note": "",
                "eta_from": "14:00",
                "eta_until": "17:00",
            },
            "error": None
        }


# Singleton instance
_shipping_client = None


def get_shipping_client() -> ShippingAPIClient:
    """Get or create shipping API client singleton."""
    global _shipping_client
    if _shipping_client is None:
        _shipping_client = ShippingAPIClient()
    return _shipping_client


# Backward compatibility function
def get_shipment_status(order_id: str) -> str:
    """Legacy function - returns formatted string for simple cases."""
    client = get_shipping_client()
    result = client.get_shipment_status(order_id)

    if result["success"]:
        status = result["status"]
        details = result.get("details", {})

        if status == "in_transit":
            desc = details.get("status_description", "Onderweg")
            return f"✅ Je zending #{order_id} is onderweg! Status: {desc}."
        elif status == "delivered":
            date = details.get("date", "")
            return f"✅ Je zending #{order_id} is afgeleverd op {date}!"
        elif status == "at_depot":
            desc = details.get("status_description", "Bij depot")
            return f"📦 Je zending #{order_id}: {desc}"
        else:
            return f"📦 Status zending #{order_id}: {status}"
    else:
        error = result.get("error", "Onbekende fout")
        if result["status"] == "not_found":
            return f"❌ Zending #{order_id} niet gevonden. Controleer het zendingnummer."
        return f"❌ Kon status niet ophalen: {error}"
