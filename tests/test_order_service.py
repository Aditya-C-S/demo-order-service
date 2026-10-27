"""Integration and end-to-end unit tests for OrderService operations."""

import pytest
from src.config import INJECT_DEMO_FAILURE
from src.exceptions import ValidationError
from src.order_service import cancel_order, create_order


def test_create_order_end_to_end_success():
    """Verify standard happy path order creation and financial calculation."""
    payload = {
        "customer_id": "CUST-1001",
        "region": "US-CA",
        "items": [
            {"sku": "SKU-MONITOR-4K", "unit_price": 400.0, "quantity": 1},
            {"sku": "SKU-HDMI-CABLE", "unit_price": 20.0, "quantity": 2},
        ],
        "discount_code": "SAVE10",
        "payment_method": "credit_card",
    }

    order = create_order(payload)

    assert order["status"] == "CONFIRMED"
    assert order["order_id"].startswith("ORD-")
    fin = order["financials"]
    assert fin["subtotal"] == 440.0
    assert fin["discount_applied"] == 44.0  # 10% of 440
    # Taxable amount = 440 - 44 = 396; US-CA tax rate = 0.0975 -> 396 * 0.0975 = 38.61
    assert fin["tax_rate"] == 0.0975
    assert fin["tax_amount"] == 38.61
    assert fin["grand_total"] == 434.61


def test_order_flat_discount_and_regional_tax():
    """Verify flat discount and French EU tax rate calculation."""
    payload = {
        "customer_id": "CUST-2002",
        "region": "EU-FR",
        "items": [
            {"sku": "SKU-DESK", "unit_price": 250.0, "quantity": 1},
        ],
        "discount_code": "FLAT50",
    }

    order = create_order(payload)
    fin = order["financials"]
    assert fin["subtotal"] == 250.0
    assert fin["discount_applied"] == 50.0
    # Taxable = 200.0, EU-FR tax = 0.20 -> tax_amount = 40.0, grand_total = 240.0
    assert fin["tax_amount"] == 40.0
    assert fin["grand_total"] == 240.0


def test_cancel_existing_order():
    """Verify order cancellation updates status and timestamp."""
    payload = {
        "customer_id": "CUST-3003",
        "items": [{"sku": "SKU-CHAIR", "unit_price": 150.0, "quantity": 1}],
    }
    order = create_order(payload)
    order_id = order["order_id"]

    cancelled = cancel_order(order_id, reason="Customer duplicate order")
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["cancellation_reason"] == "Customer duplicate order"
    assert "cancelled_at" in cancelled


def test_cancel_nonexistent_order_raises():
    """Verify cancelling unknown order raises ValidationError."""
    with pytest.raises(ValidationError, match="does not exist"):
        cancel_order("ORD-NONEXISTENT-999")


def test_controlled_failure_scenario():
    """
    Controlled Demo Failure Switch:
    When INJECT_DEMO_FAILURE is active in the environment (e.g., in a failing demo PR or workflow run),
    this test triggers a deliberate test assertion failure with a clean Pytest error signature.
    """
    if INJECT_DEMO_FAILURE:
        pytest.fail(
            "Controlled CI/CD Demo Failure: Simulated build failure active via INJECT_DEMO_FAILURE=1. "
            "AssertionError: Expected order financial reconciliation to match 100% audit tolerance."
        )
