"""Shipping status API module - Delivery Company Integration."""
import logging
import os
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ShippingAPIClient:
    """Client for delivery company shipping API."""

    def __init__(self):
        self.api_key = os.getenv('SHIPPING_API_KEY', '')
        self.api_url = os.getenv('SHIPPING_API_URL', 'https://api.delivery-company.com')
        self.use_mock = not self.api_key  # Auto-enable mock if no key

        if self.use_mock:
            logger.warning("SHIPPING_API_KEY not set - using mock responses")

    def get_shipment_status(self, tracking_code: str) -> Dict[str, Any]:
        """
        Get shipment status from delivery API.

        Args:
            tracking_code: Tracking/order number from user

        Returns:
            Dict with keys: success (bool), status (str), details (dict), error (str)
        """
        if self.use_mock:
            return self._mock_response(tracking_code)

        try:
            # TODO: Implement based on actual API docs
            response = requests.get(
                f"{self.api_url}/track/{tracking_code}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "status": data.get("status", "unknown"),
                    "details": data,
                    "error": None
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "status": "not_found",
                    "details": {},
                    "error": "Order not found in shipping system"
                }
            else:
                return {
                    "success": False,
                    "status": "error",
                    "details": {},
                    "error": f"API returned {response.status_code}"
                }

        except requests.RequestException as e:
            logger.error("Shipping API error: %s", e)
            return {
                "success": False,
                "status": "error",
                "details": {},
                "error": "Could not connect to shipping provider"
            }

    def _mock_response(self, tracking_code: str) -> Dict[str, Any]:
        """Mock response for testing without API key."""
        return {
            "success": True,
            "status": "in_transit",
            "details": {
                "tracking_code": tracking_code,
                "estimated_delivery": "2026-02-15",
                "location": "Distribution center Utrecht"
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
            location = details.get("location", "onbekend")
            delivery = details.get("estimated_delivery", "")
            return f"✅ Je bestelling #{order_id} is onderweg! Huidige locatie: {location}. Verwachte levering: {delivery}."
        elif status == "delivered":
            return f"✅ Je bestelling #{order_id} is afgeleverd!"
        else:
            return f"📦 Status bestelling #{order_id}: {status}"
    else:
        error = result.get("error", "Onbekende fout")
        if result["status"] == "not_found":
            return f"❌ Bestelling #{order_id} niet gevonden in het tracking systeem. Controleer het bestelnummer."
        return f"❌ Kon tracking info niet ophalen: {error}"
