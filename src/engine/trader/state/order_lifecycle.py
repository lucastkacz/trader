"""Local order-leg lifecycle statuses and transition rules."""

from enum import StrEnum


class LegOrderStatus(StrEnum):
    """Execution lifecycle status for one spread leg target."""

    TARGET_RECORDED = "TARGET_RECORDED"
    SUBMIT_REQUESTED = "SUBMIT_REQUESTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


TERMINAL_LEG_ORDER_STATUSES = frozenset(
    {
        LegOrderStatus.FILLED,
        LegOrderStatus.CANCELLED,
        LegOrderStatus.FAILED,
        LegOrderStatus.REJECTED,
    }
)

_ALLOWED_TRANSITIONS: dict[LegOrderStatus, frozenset[LegOrderStatus]] = {
    LegOrderStatus.TARGET_RECORDED: frozenset(
        {
            LegOrderStatus.SUBMIT_REQUESTED,
            LegOrderStatus.FAILED,
        }
    ),
    LegOrderStatus.SUBMIT_REQUESTED: frozenset(
        {
            LegOrderStatus.ACKNOWLEDGED,
            LegOrderStatus.CANCEL_REQUESTED,
            LegOrderStatus.FAILED,
            LegOrderStatus.REJECTED,
        }
    ),
    LegOrderStatus.ACKNOWLEDGED: frozenset(
        {
            LegOrderStatus.PARTIALLY_FILLED,
            LegOrderStatus.FILLED,
            LegOrderStatus.CANCEL_REQUESTED,
            LegOrderStatus.FAILED,
        }
    ),
    LegOrderStatus.PARTIALLY_FILLED: frozenset(
        {
            LegOrderStatus.PARTIALLY_FILLED,
            LegOrderStatus.FILLED,
            LegOrderStatus.CANCEL_REQUESTED,
            LegOrderStatus.FAILED,
        }
    ),
    LegOrderStatus.CANCEL_REQUESTED: frozenset(
        {
            LegOrderStatus.CANCELLED,
            LegOrderStatus.FAILED,
        }
    ),
    LegOrderStatus.FILLED: frozenset(),
    LegOrderStatus.CANCELLED: frozenset(),
    LegOrderStatus.FAILED: frozenset(),
    LegOrderStatus.REJECTED: frozenset(),
}


class InvalidLegOrderTransition(ValueError):
    """Raised when a leg status transition is not valid."""


def normalize_leg_order_status(status: LegOrderStatus | str) -> LegOrderStatus:
    """Convert a status string into the canonical enum."""
    try:
        return LegOrderStatus(status)
    except ValueError as exc:
        allowed = ", ".join(status.value for status in LegOrderStatus)
        raise ValueError(f"Unknown leg order status {status!r}. Expected one of: {allowed}") from exc


def validate_leg_order_transition(
    current_status: LegOrderStatus | str,
    next_status: LegOrderStatus | str,
) -> tuple[LegOrderStatus, LegOrderStatus]:
    """Validate and normalize a leg order status transition."""
    current = normalize_leg_order_status(current_status)
    next_ = normalize_leg_order_status(next_status)
    if next_ in _ALLOWED_TRANSITIONS[current]:
        return current, next_

    allowed = ", ".join(status.value for status in sorted(_ALLOWED_TRANSITIONS[current]))
    if not allowed:
        allowed = "none"
    raise InvalidLegOrderTransition(
        f"Invalid leg order transition {current.value} -> {next_.value}; "
        f"allowed next statuses: {allowed}"
    )
