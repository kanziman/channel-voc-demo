#!/usr/bin/env python3
"""assumptions.py — the transparent ₩ impact model.

Honesty rule (handoff §9): the *counts* are real (measured from the actual
conversations). The *money conversion* is an explicit, sourced assumption model —
never a fabricated fact. Every constant below carries a `basis` string and is
surfaced verbatim in the dashboard's "Assumptions" panel so a stakeholder can
audit or override it. Change a number here and the whole ₩ figure re-derives.

revenue_at_risk(category) = count × at_risk_rate × value_per_case_krw
"""
from __future__ import annotations

# Global economic assumptions (mid-size Korean D2C commerce). Labelled ASSUMPTION.
AOV_KRW = 55_000          # assumed average order value
FX_USD_KRW = 1_350        # display helper only

# Recovery rate: fraction of at-risk ₩ a timely, correct action actually saves.
# Assumption grounded in the service-recovery paradox — a well-handled failure
# retains a large share of otherwise-lost customers (TARP/Goodman). Conservative.
RECOVERY_RATE = 0.35


def projected_recoverable_krw(revenue_at_risk_krw: int) -> int:
    """₩ plausibly saved if the dispatched actions land (stated assumption)."""
    return int(round(revenue_at_risk_krw * RECOVERY_RATE))

# Public benchmarks used to justify the at-risk rates (cited, not invented):
#  - Baymard Institute: average documented cart/checkout abandonment ≈ 70.19%
#    (49 studies). https://baymard.com/lists/cart-abandonment-rate
#  - Invesp / classic retention economics: acquiring a new customer costs ~5×
#    retaining one. https://www.invespcro.com/blog/customer-acquisition-retention/
#  - A resolved complaint retains a customer far more often than an ignored one
#    (service-recovery paradox, TARP/Goodman studies).
#
# `at_risk_rate` = fraction of conversations in the category that plausibly sit on
# real revenue (conservative, stated as assumption). `value_per_case_krw` = the ₩
# exposed per at-risk conversation.
CATEGORY_MODEL: dict[str, dict] = {
    "PAYMENT": {
        "at_risk_rate": 0.55,
        "value_per_case_krw": AOV_KRW,          # a blocked payment = a lost order
        "severity": "high",
        "mechanism": "Payment friction blocks a purchase already in the cart.",
        "basis": "Checkout abandonment ~70% (Baymard); we take a conservative 55% "
                 "as directly revenue-blocking. Value = 1 AOV lost.",
    },
    "ORDER": {
        "at_risk_rate": 0.40,
        "value_per_case_krw": int(AOV_KRW * 0.9),
        "severity": "high",
        "mechanism": "Order placement/tracking failures stall an in-flight order.",
        "basis": "40% of order-stage tickets assumed to gate an order; value ≈ 0.9 AOV.",
    },
    "REFUND": {
        "at_risk_rate": 0.50,
        "value_per_case_krw": int(AOV_KRW * 1.2),
        "severity": "high",
        "mechanism": "A mishandled refund is the #1 trigger of churn + chargebacks.",
        "basis": "Retention economics: a lost customer forfeits repeat LTV (~1.2 AOV "
                 "near-term); acquiring a replacement costs ~5× (Invesp).",
    },
    "CANCEL": {
        "at_risk_rate": 0.60,
        "value_per_case_krw": int(AOV_KRW * 1.5),
        "severity": "high",
        "mechanism": "Cancellation intent is an explicit churn signal; save-flow ROI.",
        "basis": "60% treated as genuine churn risk; forfeited near-term LTV ≈ 1.5 AOV.",
    },
    "SUBSCRIPTION": {
        "at_risk_rate": 0.55,
        "value_per_case_krw": int(AOV_KRW * 2.0),
        "severity": "high",
        "mechanism": "Subscription issues threaten recurring revenue (multi-period LTV).",
        "basis": "Recurring revenue: one lapsed subscriber ≈ 2 AOV of forward value.",
    },
    "DELIVERY": {
        "at_risk_rate": 0.35,
        "value_per_case_krw": int(AOV_KRW * 0.6),
        "severity": "medium",
        "mechanism": "Late/failed delivery erodes repeat-purchase probability.",
        "basis": "35% assumed to depress the next order; value ≈ 0.6 AOV of repeat risk.",
    },
    "SHIPPING": {
        "at_risk_rate": 0.30,
        "value_per_case_krw": int(AOV_KRW * 0.5),
        "severity": "medium",
        "mechanism": "Shipping cost/option friction abandons carts pre-payment.",
        "basis": "Unexpected shipping cost is a top-3 abandonment reason (Baymard).",
    },
    "INVOICE": {
        "at_risk_rate": 0.20,
        "value_per_case_krw": int(AOV_KRW * 0.3),
        "severity": "medium",
        "mechanism": "Invoice/billing confusion drives disputes and support load.",
        "basis": "20% assumed to escalate to a billing dispute; value ≈ 0.3 AOV.",
    },
    "ACCOUNT": {
        "at_risk_rate": 0.15,
        "value_per_case_krw": int(AOV_KRW * 0.3),
        "severity": "medium",
        "mechanism": "Login/registration walls block returning buyers from converting.",
        "basis": "15% of account friction assumed to block a session that would buy.",
    },
    "CONTACT": {
        "at_risk_rate": 0.10,
        "value_per_case_krw": int(AOV_KRW * 0.2),
        "severity": "low",
        "mechanism": "Inability to reach an agent compounds any underlying issue.",
        "basis": "Deflection risk; small direct ₩, high frustration multiplier.",
    },
    "FEEDBACK": {
        "at_risk_rate": 0.10,
        "value_per_case_krw": int(AOV_KRW * 0.2),
        "severity": "low",
        "mechanism": "Complaints/feedback are leading indicators, not direct loss.",
        "basis": "Signal value; conservatively priced low to avoid double-counting.",
    },
}

DEFAULT_MODEL = {
    "at_risk_rate": 0.15,
    "value_per_case_krw": int(AOV_KRW * 0.3),
    "severity": "low",
    "mechanism": "Uncategorised friction.",
    "basis": "Fallback assumption for unmapped categories.",
}


# ── Intent-level risk weighting ──────────────────────────────────────────────
# A category is too coarse to price: within REFUND, "get_refund" is real exposure
# but "check_refund_policy" is an information request. Each conversation is priced
# by its (predicted) intent so an inbox of "how do I unsubscribe from the
# newsletter" is NOT billed as paid-subscriber churn. Weight multiplies the
# category's value_per_case. Tiers: informational 0.2, friction 1.0, churn 1.2.
_INFO = 0.2      # information request — low direct ₩
_FRICTION = 1.0  # a transaction is blocked/breaking — full exposure
_CHURN = 1.2     # explicit dissatisfaction / leaving — retention exposure
INTENT_WEIGHT: dict[str, float] = {
    # informational — asking for info / status, no blocked transaction
    "check_invoice": _INFO, "get_invoice": _INFO, "check_payment_methods": _INFO,
    "newsletter_subscription": _INFO, "delivery_period": _INFO, "delivery_options": _INFO,
    "check_refund_policy": _INFO, "check_cancellation_fee": _INFO, "track_order": _INFO,
    "track_refund": _INFO, "contact_customer_service": _INFO, "contact_human_agent": _INFO,
    "review": _INFO, "set_up_shipping_address": _INFO, "change_shipping_address": _INFO,
    "create_account": _INFO, "edit_account": _INFO, "switch_account": _INFO,
    # friction — a transaction is blocked or breaking
    "payment_issue": _FRICTION, "registration_problems": _FRICTION, "place_order": _FRICTION,
    "change_order": _FRICTION, "cancel_order": _FRICTION, "recover_password": _FRICTION,
    # churn / dissatisfaction — money back or leaving
    "complaint": _CHURN, "delete_account": _CHURN, "get_refund": _CHURN,
}
DEFAULT_INTENT_WEIGHT = 0.6


def intent_weight(intent: str | None) -> float:
    return INTENT_WEIGHT.get((intent or "").strip(), DEFAULT_INTENT_WEIGHT)


def model_for(category: str) -> dict:
    return CATEGORY_MODEL.get(category.upper(), DEFAULT_MODEL)


def conversation_risk_krw(category: str, intent: str | None) -> float:
    """₩ exposed by a single conversation = category value × intent weight."""
    return model_for(category)["value_per_case_krw"] * intent_weight(intent)


def revenue_at_risk_krw(category: str, count: int) -> int:
    """Legacy category-only estimate (used only when intents are unavailable)."""
    m = model_for(category)
    return int(round(count * m["at_risk_rate"] * m["value_per_case_krw"]))


def assumptions_manifest() -> dict:
    """Everything the dashboard needs to render an auditable Assumptions panel."""
    return {
        "globals": {
            "aov_krw": AOV_KRW,
            "fx_usd_krw": FX_USD_KRW,
            "note": "Counts are measured from real conversations; ₩ conversion is an "
                    "explicit assumption model. Each conversation is priced by its "
                    "predicted intent (informational 0.2× / friction 1.0× / churn 1.2×) "
                    "so information requests are not billed as churn. Edit assumptions.py to re-derive.",
            "intent_tiers": {"informational": _INFO, "friction": _FRICTION, "churn": _CHURN,
                             "default": DEFAULT_INTENT_WEIGHT},
        },
        "recovery_rate": RECOVERY_RATE,
        "sources": [
            {"claim": "Cart/checkout abandonment ≈ 70.19%",
             "source": "Baymard Institute (49-study average)",
             "url": "https://baymard.com/lists/cart-abandonment-rate"},
            {"claim": "Acquiring a new customer costs ~5× retaining one",
             "source": "Invesp — customer acquisition vs retention",
             "url": "https://www.invespcro.com/blog/customer-acquisition-retention/"},
            {"claim": f"A resolved failure recovers a large share of at-risk customers "
                      f"(recovery rate assumed {RECOVERY_RATE:.0%})",
             "source": "Service-recovery paradox (TARP/Goodman)",
             "url": "https://www.serviceexcellence.co.uk/goodman"},
        ],
        "categories": {k: v for k, v in CATEGORY_MODEL.items()},
    }
