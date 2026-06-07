"""Plan limits and enforcement."""

from app.constants.escalation_stages import PLAN_LIMITS, PLAN_ORDER
from app.exceptions import PlanLimitError
from app.models import Plan, User


def enforce_plan_limit(user: User, active_count: int) -> None:
    limit = PLAN_LIMITS[user.plan]
    if limit is not None and active_count >= limit:
        required = "STARTER" if user.plan == Plan.FREE else "PRO"
        raise PlanLimitError(
            f"Plan limit reached ({limit} active enforcement cases). Upgrade to continue.",
            required_plan=required,
        )


def require_plan(user: User, min_plan: Plan) -> None:
    if PLAN_ORDER[user.plan] < PLAN_ORDER[min_plan]:
        raise PlanLimitError(
            f"Upgrade required. This feature needs the {min_plan.value} plan.",
            required_plan=min_plan.value,
        )
