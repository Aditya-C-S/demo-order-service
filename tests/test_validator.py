"""Unit tests for validator module in demo-order-service."""

import pytest
from src.exceptions import InventoryError, ValidationError
from src.validator import (
    calculate_tax_rate,
    validate_item_structure,
    validate_order_payload,
)


def test_validate_item_structure_success():
    """Verify standard valid line item conforms to schema."""
    valid_item = {"sku": "SKU-LAPTOP-01", "unit_price": 999.99, "quantity": 2}
    assert validate_item_structure(valid_item) is True


def test_validate_item_structure_invalid_sku():
    """Verify missing SKU triggers ValidationError."""
    with pytest.raises(ValidationError, match="Missing or invalid line item 'sku'"):
        validate_item_structure({"unit_price": 50.0, "quantity": 1})


def test_validate_item_structure_negative_price():
    """Verify negative price triggers ValidationError."""
    with pytest.raises(ValidationError, match="Invalid unit price"):
        validate_item_structure({"sku": "SKU-TEST", "unit_price": -10.0, "quantity": 1})


def test_validate_item_structure_excessive_quantity():
    """Verify quantities beyond threshold trigger InventoryError."""
    with pytest.raises(InventoryError, match="exceeds maximum allowable threshold"):
        validate_item_structure({"sku": "SKU-BULK", "unit_price": 10.0, "quantity": 999})


def test_calculate_tax_rate_known_regions():
    """Verify accurate regional tax lookup."""
    assert calculate_tax_rate("US-CA") == 0.0975
    assert calculate_tax_rate("US-NY") == 0.08875
    assert calculate_tax_rate("EU-DE") == 0.19


def test_calculate_tax_rate_default_fallback():
    """Verify fallback to default tax rate for unknown jurisdictions."""
    assert calculate_tax_rate("UNKNOWN-ZONE") == 0.08
    assert calculate_tax_rate("") == 0.08


def test_validate_order_payload_success():
    """Verify valid order payload succeeds."""
    payload = {
        "customer_id": "CUST-9876",
        "items": [
            {"sku": "SKU-MOUSE", "unit_price": 25.0, "quantity": 1},
            {"sku": "SKU-KEYBOARD", "unit_price": 75.0, "quantity": 1},
        ],
        "payment_method": "credit_card",
    }
    assert validate_order_payload(payload) is True


def test_validate_order_payload_empty_items():
    """Verify order with empty items list is rejected."""
    payload = {"customer_id": "CUST-1", "items": []}
    with pytest.raises(ValidationError, match="must contain at least one line item"):
        validate_order_payload(payload)


def test_validate_order_payload_unsupported_payment():
    """Verify invalid payment method is rejected."""
    payload = {
        "customer_id": "CUST-1",
        "items": [{"sku": "SKU-1", "unit_price": 10.0, "quantity": 1}],
        "payment_method": "unsupported_token_exchange",
    }
    with pytest.raises(ValidationError, match="Unsupported payment method"):
        validate_order_payload(payload)
