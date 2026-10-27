"""Validation logic and schema enforcement for incoming order requests."""

from typing import Any, Dict, List
from src.config import (
    INJECT_DEMO_FAILURE,
    MAX_ITEM_QUANTITY,
    MAX_ORDER_AMOUNT,
    REGIONAL_TAX_RATES,
    DEFAULT_TAX_RATE,
    VALID_PAYMENT_METHODS,
)
from src.exceptions import InventoryError, ValidationError


def validate_item_structure(item: Dict[str, Any]) -> bool:
    """Validate individual line item properties."""
    if not isinstance(item, dict):
        raise ValidationError("Line item must be a valid JSON dictionary.")

    sku = item.get("sku")
    if not sku or not isinstance(sku, str):
        raise ValidationError("Missing or invalid line item 'sku'.")

    price = item.get("unit_price")
    if price is None or not isinstance(price, (int, float)) or price < 0:
        raise ValidationError(f"Invalid unit price for SKU '{sku}': {price}")

    qty = item.get("quantity")
    if qty is None or not isinstance(qty, int) or qty <= 0:
        raise ValidationError(f"Invalid quantity for SKU '{sku}': {qty}")

    if qty > MAX_ITEM_QUANTITY:
        raise InventoryError(f"Requested quantity {qty} exceeds maximum allowable threshold ({MAX_ITEM_QUANTITY}).")

    return True


def calculate_tax_rate(region: str) -> float:
    """Lookup regional tax rates for geographic jurisdictions."""
    if not region or not isinstance(region, str):
        return DEFAULT_TAX_RATE
    clean_region = region.strip().upper()
    return REGIONAL_TAX_RATES.get(clean_region, DEFAULT_TAX_RATE)


def validate_order_payload(payload: Dict[str, Any]) -> bool:
    """
    Validate top-level order payload structure, line items, and payment options.
    If INJECT_DEMO_FAILURE is active, raises ValidationError to simulate a CI failure.
    """
    if INJECT_DEMO_FAILURE:
        raise ValidationError(
            "Controlled CI/CD Demo Failure: Order validation rejected. "
            "Field 'billing_address.postal_code' failed strict regex gatekeeper check."
        )

    if not isinstance(payload, dict):
        raise ValidationError("Order payload must be a JSON object.")

    customer_id = payload.get("customer_id")
    if not customer_id or not isinstance(customer_id, str):
        raise ValidationError("Required field 'customer_id' is missing or not a string.")

    items = payload.get("items")
    if not items or not isinstance(items, list) or len(items) == 0:
        raise ValidationError("Order must contain at least one line item in 'items'.")

    for item in items:
        validate_item_structure(item)

    payment_method = payload.get("payment_method")
    if payment_method and payment_method not in VALID_PAYMENT_METHODS:
        raise ValidationError(f"Unsupported payment method: '{payment_method}'.")

    return True
