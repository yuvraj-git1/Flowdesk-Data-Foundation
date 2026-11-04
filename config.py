"""Flowdesk world configuration: single source of truth for constants.

Every later stage imports from here. Change a number here, rebuild, and the
whole world shifts consistently.
"""

SEED = 20230101                      # one master seed; stages derive child seeds from it
START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
SNAPSHOT_DATE = "2025-12-31"         # "as of" date for current-state columns

# ---- Pricing ---------------------------------------------------------------
PLANS = {
    "free":     {"seat_price_usd_month": 0.00,  "max_users": 5},
    "pro":      {"seat_price_usd_month": 12.00, "max_users": None},
    "business": {"seat_price_usd_month": 24.00, "max_users": None},
}
ANNUAL_DISCOUNT = 0.20               # annual price = list * (1 - 0.20), billed upfront for 12 months

# ---- Calibration targets (Stage 2-4 generators tune towards these) ---------
TARGETS = {
    "signups": 40_000,               # accounts created (incl. ~2.5% duplicates, B4)
    "ever_paid_accounts": 4_000,     # ASSUMPTION: "~4K paid" = ever paid; ~3.2K still active at end
    "end_arr_usd": 6_000_000,
    "self_serve_share": 0.85,
    "sales_assisted_share": 0.15,
    "payment_failure_rate": 0.04,
    "dunning_retry_days": (1, 3, 7),  # attempts at day 0, then retries on days 1, 3, 7
    "aha_retention_12w": {"invited_within_3d": 0.55, "not_invited": 0.20},
    "events_rows": (3_000_000, 4_000_000),
}

# ---- Planted problem magnitudes (used in Stage 5 and the answer key) -------
PLANTED = {
    "B1": dict(window=("2025-02-01", "2025-06-30"), accounts=300, arr_usd=450_000),
    "B2": dict(window=("2024-09-01", "2025-01-31"), accounts=140, arr_usd=180_000),
    "B3": dict(share_of_business_accounts=0.08, arr_usd=220_000),
    "B4": dict(share_of_accounts=0.025),
    "B6": dict(window=("2025-03-03", "2025-03-09"), accounts=25),
    "B7": dict(share_of_refunds=0.004),
    "P2": dict(observed_split=(0.523, 0.477), planned_split=(0.5, 0.5)),
    "P5": dict(platform="android", app_version="4.2.x", weeks=3),
    "G1": dict(paid_social_overcount=1.6, paid_search_overcount=1.3),
    "G3": dict(sales_assisted_ltv_multiple=3.0),
    "G4": dict(messy_label_share=0.15),
}

# ---- Enumerations (documented in the data dictionary) ----------------------
ENUMS = {
    "plan": ["free", "pro", "business"],
    "billing_interval": ["monthly", "annual"],
    "motion": ["self_serve", "sales_assisted"],
    "lifecycle_stage": ["free", "paid", "churned"],
    "company_size_band": ["1-10", "11-50", "51-200", "201-1000", "1000+"],
    "industry": ["software", "agency", "marketing", "education", "finance",
                 "healthcare", "retail", "manufacturing", "nonprofit", "other"],
    "currency": ["USD", "EUR", "GBP", "CAD", "INR"],
    "role": ["owner", "admin", "member"],
    "platform": ["web", "ios", "android"],
    "event_name": ["signup_completed", "session_start", "project_created", "task_created",
                   "task_completed", "task_assigned", "comment_added", "teammate_invited",
                   "invite_accepted", "integration_connected", "paywall_viewed",
                   "upgrade_clicked", "checkout_started", "subscription_started"],
    "subscription_status": ["active", "past_due", "canceled"],
    "cancellation_source": ["user", "payment_failure", "admin"],
    "plan_change_type": ["start_paid", "upgrade", "downgrade", "interval_switch",
                         "seat_change", "cancel"],
    "initiated_by": ["customer", "sales", "system"],
    "billing_reason": ["subscription_create", "subscription_cycle", "subscription_update", "manual"],
    "invoice_status": ["paid", "void", "uncollectible"],
    "payment_status": ["succeeded", "failed"],
    "failure_code": ["card_declined", "insufficient_funds", "expired_card", "processor_error"],
    "payment_method": ["card", "ach", "wire"],
    "refund_reason": ["requested_by_customer", "duplicate_charge", "service_issue", "goodwill", "fraud"],
    "refund_status": ["succeeded", "pending", "failed"],
    "discount_type": ["percent", "fixed"],
    "coupon_duration": ["once", "repeating", "forever"],
    "redemption_channel": ["checkout", "sales_rep", "support"],
    "variant": ["control", "treatment"],
    "experiment_unit": ["user", "account"],
    "experiment_status": ["completed", "running", "stopped_early"],
    "paid_channel": ["paid_search", "paid_social", "review_site", "affiliate"],
    "lead_status": ["new", "mql", "sql", "opportunity", "won", "lost"],
    "touch_type": ["email", "call", "demo", "trial_extension", "contract_sent"],
    "touch_outcome": ["no_response", "replied", "meeting_booked", "positive", "negative"],
    "attribution_model": ["click_7d_view_1d", "click_28d", "click_30d_view_7d"],
}
