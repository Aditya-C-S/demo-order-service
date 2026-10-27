"""Application configuration and runtime switches for demo-order-service."""

import os

# Feature switch: Set INJECT_DEMO_FAILURE=1 (or true) in the environment
# to trigger controlled validation failure for CI/CD demonstration
INJECT_DEMO_FAILURE: bool = os.getenv("INJECT_DEMO_FAILURE", "0").lower() in ("1", "true", "yes")

# Currency and Tax Configuration
CURRENCY: str = "USD"
CURRENCY_PRECISION: int = 2
DEFAULT_TAX_RATE: float = 0.08
REGIONAL_TAX_RATES: dict[str, float] = {
    "US-CA": 0.0975,
    "US-NY": 0.08875,
    "US-TX": 0.0825,
    "US-WA": 0.065,
    "EU-DE": 0.19,
    "EU-FR": 0.20,
}

# Business threshold limits
MAX_ITEM_QUANTITY: int = 100
MAX_ORDER_AMOUNT: float = 50000.0
VALID_PAYMENT_METHODS: set[str] = {"credit_card", "debit_card", "bank_transfer", "crypto_escrow"}
