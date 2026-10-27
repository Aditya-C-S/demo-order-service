"""Order processing, calculation, and tax computation routines."""

from typing import Any, Dict
from src.config import CURRENCY, CURRENCY_PRECISION, MAX_ORDER_AMOUNT
from src.exceptions import PricingError
from src.validator import calculate_tax_rate, validate_item_structure


def apply_discount(subtotal: float, discount_code: str) -> float:
    """Calculate discount amount based on approved promotional codes."""
    if not discount_code or not isinstance(discount_code, str):
        return 0.0

    code = discount_code.strip().upper()
    if code == "SAVE10":
        return round(subtotal * 0.10, CURRENCY_PRECISION)
    elif code == "SAVE20":
        return round(subtotal * 0.20, CURRENCY_PRECISION)
    elif code == "FLAT50":
        return min(50.0, subtotal)
    return 0.0


def compute_order_totals(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute subtotal, applicable taxes, discount, and grand total.
    Invokes validator routines to ensure line items and regional taxes conform to spec.
    """
    items = order_data.get("items", [])
    subtotal = 0.0

    for item in items:
        validate_item_structure(item)
        subtotal += item["unit_price"] * item["quantity"]

    subtotal = round(subtotal, CURRENCY_PRECISION)
    if subtotal > MAX_ORDER_AMOUNT:
        raise PricingError(f"Calculated subtotal ${subtotal} exceeds maximum authorized limit (${MAX_ORDER_AMOUNT}).")

    discount_code = order_data.get("discount_code", "")
    discount_amount = apply_discount(subtotal, discount_code)

    taxable_amount = max(0.0, subtotal - discount_amount)
    region = order_data.get("region", "US-CA")
    tax_rate = calculate_tax_rate(region)
    tax_amount = round(taxable_amount * tax_rate, CURRENCY_PRECISION)

    grand_total = round(taxable_amount + tax_amount, CURRENCY_PRECISION)

    return {
        "currency": CURRENCY,
        "subtotal": subtotal,
        "discount_applied": discount_amount,
        "discount_code": discount_code if discount_amount > 0 else None,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "grand_total": grand_total,
    }
