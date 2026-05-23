"""SLA tier decorator tests."""

from __future__ import annotations

import pytest

from verolas_api.middleware.sla import get_tier, sla_tier


def test_sla_tier_attaches_attribute() -> None:
    @sla_tier(2)
    async def handler() -> None:
        pass

    assert get_tier(handler) == 2


def test_sla_tier_rejects_unknown_tier() -> None:
    with pytest.raises(ValueError, match="SLA tier must be one of"):

        @sla_tier(5)
        async def handler() -> None:
            pass


def test_get_tier_returns_none_for_undecorated() -> None:
    async def handler() -> None:
        pass

    assert get_tier(handler) is None
