"""Named placeholders for capability contracts implemented in later plans."""

from __future__ import annotations

PENDING_CAPABILITY_CONTRACTS: dict[str, str] = {}


def unimplemented_capability_contract(capability: str) -> None:
    plan = PENDING_CAPABILITY_CONTRACTS.get(capability)
    if plan is None:
        raise KeyError(f"{capability} is not a pending capability contract")
    raise NotImplementedError(
        f"{capability} contract is implemented in plan {plan}; "
        "do not mark this capability as passing"
    )
