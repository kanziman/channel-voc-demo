"""Controlled vocabularies for extraction (single source of truth).

INTENTS: the 27-class Bitext label space (must match sklearn classes_ exactly,
so the LLM arm and the sklearn baseline are compared on identical labels).
COMPONENTS: a tight product-surface vocabulary. Symptoms IMPLICATE a Component;
repeated implication of one Component is what promotes a RootCause (§2.1) — so
this set is deliberately small to make aggregation meaningful, not fragmented.
INTENT_TO_COMPONENT gives a deterministic fallback when the LLM omits/echoes.
"""
from __future__ import annotations

INTENTS = [
    "cancel_order", "change_order", "change_shipping_address", "check_cancellation_fee",
    "check_invoice", "check_payment_methods", "check_refund_policy", "complaint",
    "contact_customer_service", "contact_human_agent", "create_account", "delete_account",
    "delivery_options", "delivery_period", "edit_account", "get_invoice", "get_refund",
    "newsletter_subscription", "payment_issue", "place_order", "recover_password",
    "registration_problems", "review", "set_up_shipping_address", "switch_account",
    "track_order", "track_refund",
]

# 11 coarse Bitext categories (kept for Theme rollup + sklearn category baseline).
CATEGORIES = [
    "ACCOUNT", "CANCEL", "CONTACT", "DELIVERY", "FEEDBACK", "INVOICE",
    "ORDER", "PAYMENT", "REFUND", "SHIPPING", "SUBSCRIPTION",
]

COMPONENTS = [
    "auth",          # account creation, login, password, registration, edit/switch/delete
    "checkout",      # placing orders, payment methods, payment failures
    "orders",        # order tracking, changes, cancellations
    "shipping",      # shipping address, delivery options/period
    "billing",       # invoices, refunds, cancellation fees
    "subscription",  # newsletter / plan subscription
    "support",       # contacting a human / customer service
    "feedback",      # reviews, complaints
]

# Deterministic intent → component map (grounding + fallback).
INTENT_TO_COMPONENT = {
    "create_account": "auth", "delete_account": "auth", "edit_account": "auth",
    "switch_account": "auth", "recover_password": "auth", "registration_problems": "auth",
    "place_order": "checkout", "check_payment_methods": "checkout", "payment_issue": "checkout",
    "track_order": "orders", "change_order": "orders", "cancel_order": "orders",
    "check_cancellation_fee": "orders",
    "change_shipping_address": "shipping", "set_up_shipping_address": "shipping",
    "delivery_options": "shipping", "delivery_period": "shipping",
    "get_invoice": "billing", "check_invoice": "billing", "get_refund": "billing",
    "track_refund": "billing", "check_refund_policy": "billing",
    "newsletter_subscription": "subscription",
    "contact_human_agent": "support", "contact_customer_service": "support",
    "review": "feedback", "complaint": "feedback",
}

# Coarse category each intent rolls up to (Theme layer).
INTENT_TO_CATEGORY = {
    "create_account": "ACCOUNT", "delete_account": "ACCOUNT", "edit_account": "ACCOUNT",
    "switch_account": "ACCOUNT", "recover_password": "ACCOUNT", "registration_problems": "ACCOUNT",
    "place_order": "ORDER", "change_order": "ORDER",
    "cancel_order": "CANCEL", "check_cancellation_fee": "CANCEL",
    "check_payment_methods": "PAYMENT", "payment_issue": "PAYMENT",
    "track_order": "ORDER",
    "change_shipping_address": "SHIPPING", "set_up_shipping_address": "SHIPPING",
    "delivery_options": "DELIVERY", "delivery_period": "DELIVERY",
    "get_invoice": "INVOICE", "check_invoice": "INVOICE",
    "get_refund": "REFUND", "track_refund": "REFUND", "check_refund_policy": "REFUND",
    "newsletter_subscription": "SUBSCRIPTION",
    "contact_human_agent": "CONTACT", "contact_customer_service": "CONTACT",
    "review": "FEEDBACK", "complaint": "FEEDBACK",
}
