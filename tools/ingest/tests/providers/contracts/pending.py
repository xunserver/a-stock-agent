"""Named placeholders for capability contracts implemented in later plans.

These names exist so later Agents extend a known list. They must not be treated
as passing contracts.
"""

from __future__ import annotations

PENDING_CAPABILITY_CONTRACTS: dict[str, str] = {
    "classifications": "06-classifications-memberships",
    "memberships": "06-classifications-memberships",
    "news": "07-news-events",
    "events": "07-news-events",
}


def unimplemented_capability_contract(capability: str) -> None:
    plan = PENDING_CAPABILITY_CONTRACTS.get(capability)
    if plan is None:
        raise KeyError(f"{capability} is not a pending capability contract")
    raise NotImplementedError(
        f"{capability} contract is implemented in plan {plan}; "
        "do not mark this capability as passing"
    )
