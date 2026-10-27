"""Domain exception definitions for demo-order-service."""

class OrderServiceError(Exception):
    """Base domain exception for all order service operations."""
    pass


class ValidationError(OrderServiceError):
    """Raised when an order payload or item schema fails validation checks."""
    pass


class InventoryError(OrderServiceError):
    """Raised when item quantities violate business thresholds or inventory limits."""
    pass


class PricingError(OrderServiceError):
    """Raised during discount calculation or tax estimation discrepancies."""
    pass
