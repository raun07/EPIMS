"""Unit tests for the 3-way match engine logic."""
from __future__ import annotations

from decimal import Decimal

import pytest


class TestThreeWayMatchTolerance:
    """Test the tolerance math without needing a database."""

    def _compute_price_variance_pct(
        self, po_price: Decimal, invoice_price: Decimal
    ) -> Decimal:
        if po_price == 0:
            return Decimal("100")
        return abs(invoice_price - po_price) / po_price * Decimal("100")

    def test_exact_match_zero_variance(self):
        pct = self._compute_price_variance_pct(Decimal("100"), Decimal("100"))
        assert pct == Decimal("0")

    def test_within_2_pct_tolerance(self):
        pct = self._compute_price_variance_pct(Decimal("100"), Decimal("101.50"))
        assert pct == Decimal("1.5")
        assert pct <= Decimal("2.0")  # within tolerance

    def test_exceeds_2_pct_tolerance(self):
        pct = self._compute_price_variance_pct(Decimal("100"), Decimal("103"))
        assert pct == Decimal("3")
        assert pct > Decimal("2.0")  # fails tolerance

    def test_price_below_po_price_within_tolerance(self):
        """Credit note scenario — invoice price lower than PO."""
        pct = self._compute_price_variance_pct(Decimal("200"), Decimal("196"))
        assert pct == Decimal("2")
        assert pct <= Decimal("2.0")

    def test_zero_po_price_returns_100pct(self):
        pct = self._compute_price_variance_pct(Decimal("0"), Decimal("50"))
        assert pct == Decimal("100")


class TestQtyVariance:
    def _qty_variance(self, grn_qty: Decimal, invoice_qty: Decimal) -> Decimal:
        return abs(invoice_qty - grn_qty)

    def test_exact_qty_match(self):
        assert self._qty_variance(Decimal("10"), Decimal("10")) == Decimal("0")

    def test_short_delivery(self):
        variance = self._qty_variance(Decimal("10"), Decimal("8"))
        assert variance == Decimal("2")

    def test_over_delivery(self):
        variance = self._qty_variance(Decimal("10"), Decimal("11"))
        assert variance == Decimal("1")


class TestApprovalStatusTransitions:
    """Test PR status machine transitions."""

    def test_draft_can_submit(self):
        from app.domain.procurement.models import PR_STATUS_TRANSITIONS, PRStatus
        assert PRStatus.SUBMITTED in PR_STATUS_TRANSITIONS[PRStatus.DRAFT]

    def test_draft_can_cancel(self):
        from app.domain.procurement.models import PR_STATUS_TRANSITIONS, PRStatus
        assert PRStatus.CANCELLED in PR_STATUS_TRANSITIONS[PRStatus.DRAFT]

    def test_approved_cannot_go_back_to_draft(self):
        from app.domain.procurement.models import PR_STATUS_TRANSITIONS, PRStatus
        assert PRStatus.DRAFT not in PR_STATUS_TRANSITIONS[PRStatus.APPROVED]

    def test_po_created_is_terminal(self):
        from app.domain.procurement.models import PR_STATUS_TRANSITIONS, PRStatus
        assert PR_STATUS_TRANSITIONS[PRStatus.PO_CREATED] == []

    def test_cancelled_is_terminal(self):
        from app.domain.procurement.models import PR_STATUS_TRANSITIONS, PRStatus
        assert PR_STATUS_TRANSITIONS[PRStatus.CANCELLED] == []


class TestPOStatusTransitions:
    def test_released_can_receive(self):
        from app.domain.procurement.models import PO_STATUS_TRANSITIONS, POStatus
        assert POStatus.PARTIALLY_RECEIVED in PO_STATUS_TRANSITIONS[POStatus.RELEASED]
        assert POStatus.RECEIVED in PO_STATUS_TRANSITIONS[POStatus.RELEASED]

    def test_closed_is_terminal(self):
        from app.domain.procurement.models import PO_STATUS_TRANSITIONS, POStatus
        assert PO_STATUS_TRANSITIONS[POStatus.CLOSED] == []

    def test_draft_can_go_to_pending_or_released(self):
        from app.domain.procurement.models import PO_STATUS_TRANSITIONS, POStatus
        transitions = PO_STATUS_TRANSITIONS[POStatus.DRAFT]
        assert POStatus.PENDING_APPROVAL in transitions
        assert POStatus.RELEASED in transitions


class TestApprovalRuleAmountFilter:
    def test_rule_applies_when_no_limits(self):
        from app.domain.approval.models import ApprovalRule
        rule = ApprovalRule()
        rule.min_amount = None
        rule.max_amount = None
        assert rule.applies_to_amount(Decimal("999999")) is True

    def test_rule_applies_within_range(self):
        from app.domain.approval.models import ApprovalRule
        rule = ApprovalRule()
        rule.min_amount = Decimal("10000")
        rule.max_amount = Decimal("100000")
        assert rule.applies_to_amount(Decimal("50000")) is True

    def test_rule_does_not_apply_below_min(self):
        from app.domain.approval.models import ApprovalRule
        rule = ApprovalRule()
        rule.min_amount = Decimal("10000")
        rule.max_amount = None
        assert rule.applies_to_amount(Decimal("5000")) is False

    def test_rule_does_not_apply_above_max(self):
        from app.domain.approval.models import ApprovalRule
        rule = ApprovalRule()
        rule.min_amount = None
        rule.max_amount = Decimal("10000")
        assert rule.applies_to_amount(Decimal("50000")) is False
