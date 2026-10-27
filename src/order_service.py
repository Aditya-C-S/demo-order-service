"""Main OrderService orchestration API handling order lifecycle events."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from src.exceptions import ValidationError
from src.processor import compute_order_totals
from src.validator import validate_order_payload


class OrderService:
    """Manages order intake, financial calculation, and fulfillment dispatch."""

    def __init__(self):
        self._orders: Dict[str, Dict[str, Any]] = {}

    def create_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate, price, and record a new order submission.
        Coordinates with validate_order_payload and compute_order_totals.
        """
        # Step 1: Execute payload and schema validation
        validate_order_payload(payload)

        # Step 2: Calculate financial breakdown
        financials = compute_order_totals(payload)

        # Step 3: Construct confirmed order record
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        order_record = {
            "order_id": order_id,
            "customer_id": payload["customer_id"],
            "status": "CONFIRMED",
            "items": payload["items"],
            "region": payload.get("region", "US-CA"),
            "payment_method": payload.get("payment_method", "credit_card"),
            "financials": financials,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._orders[order_id] = order_record
        return order_record

    def cancel_order(self, order_id: str, reason: str = "Customer request") -> Dict[str, Any]:
        """Cancel an existing order if found, updating audit state."""
        if not order_id or not isinstance(order_id, str):
            raise ValidationError("Invalid order_id supplied for cancellation.")

        order = self._orders.get(order_id)
        if not order:
            raise ValidationError(f"Order '{order_id}' does not exist.")

        order["status"] = "CANCELLED"
        order["cancellation_reason"] = reason
        order["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        return order

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Retrieve current order tracking status."""
        order = self._orders.get(order_id)
        if not order:
            raise ValidationError(f"Order '{order_id}' not found.")
        return {
            "order_id": order["order_id"],
            "status": order["status"],
            "grand_total": order["financials"]["grand_total"],
        }


# Global singleton instance for convenient imports
default_order_service = OrderService()


def create_order(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Top-level convenience invocation for OrderService.create_order."""
    return default_order_service.create_order(payload)


def cancel_order(order_id: str, reason: str = "Customer request") -> Dict[str, Any]:
    """Top-level convenience invocation for OrderService.cancel_order."""
    return default_order_service.cancel_order(order_id, reason=reason)
