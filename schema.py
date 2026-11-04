"""Flowdesk schema definition (17 public tables + 5 hidden `_truth` tables).

Conventions
-----------
* Surrogate integer keys (BIGINT). No ENFORCED foreign keys: bulk loads are faster, and
  orphans/duplicates are part of the world. FKs are documented here and checked in Stage 6.
* All timestamps are UTC, stored as TIMESTAMP, *by contract*. (Reality can differ: see B5.)
* Money: DECIMAL(12,2) in the row's own `currency`, plus a *_usd companion where useful.
* `p=` on a column = internal planted-problem reference. It NEVER reaches the public dictionary.
"""
from dataclasses import dataclass, field
from typing import Optional
from config import ENUMS


@dataclass
class Col:
    name: str
    dtype: str
    desc: str
    pk: bool = False
    fk: Optional[str] = None          # "table.column"
    required: bool = False            # NOT NULL
    values: Optional[str] = None      # allowed values / format note
    p: str = ""                       # internal planted problem refs, e.g. "B1,B5"

    @property
    def not_null(self):
        return self.pk or self.required


@dataclass
class Table:
    name: str
    schema: str                       # "main" or "_truth"
    grain: str
    desc: str
    rows: str                         # approximate target row count
    stage: int                        # which build stage populates it
    cols: list = field(default_factory=list)
    composite_pk: tuple = ()

    @property
    def qname(self):
        return self.name if self.schema == "main" else f"{self.schema}.{self.name}"


def c(name, dtype, desc, *, pk=False, fk=None, req=False, vals=None, p=""):
    if isinstance(vals, list):
        vals = " | ".join(vals)
    return Col(name, dtype, desc, pk, fk, req, vals, p)


E = ENUMS
T = []

# ============================ CORE ENTITIES (Stage 2) ========================
T.append(Table("accounts", "main", "one row per workspace (team) account",
    "Every team workspace that signed up. Free and paid accounts alike.", "~41,000", 2, [
    c("account_id", "BIGINT", "Primary key.", pk=True, p=""),
    c("created_at", "TIMESTAMP", "Signup time (UTC).", req=True, p="B5"),
    c("company_name", "VARCHAR", "Company/team name as typed by the owner.", req=True, p="B4"),
    c("email_domain", "VARCHAR", "Owner's email domain; NULL for personal webmail.", p="B4"),
    c("industry", "VARCHAR", "Self-reported industry; often blank.", vals=E["industry"]),
    c("company_size_band", "VARCHAR", "Self-reported company size.", vals=E["company_size_band"]),
    c("country", "VARCHAR", "ISO-3166 alpha-2 country code.", vals="2-letter code"),
    c("billing_currency", "VARCHAR", "Currency the account is invoiced in.", req=True, vals=E["currency"], p="B5"),
    c("timezone", "VARCHAR", "Account IANA timezone.", vals="e.g. America/New_York", p="B5"),
    c("signup_source", "VARCHAR", "Raw acquisition label captured at signup; not normalized.", p="G4"),
    c("utm_source", "VARCHAR", "UTM source at signup, if any."),
    c("utm_medium", "VARCHAR", "UTM medium at signup, if any."),
    c("utm_campaign", "VARCHAR", "UTM campaign at signup, if any.", p="G1"),
    c("acquisition_motion", "VARCHAR", "How the account was acquired.", req=True, vals=E["motion"], p="G3"),
    c("lead_id", "BIGINT", "Lead record for sales-assisted accounts.", fk="leads.lead_id"),
    c("owner_user_id", "BIGINT", "User who created the account.", fk="users.user_id"),
    c("sso_enabled", "BOOLEAN", "SAML/SSO turned on (Business plan feature).", req=True, p="B3"),
    c("lifecycle_stage", "VARCHAR", "State as of snapshot date.", req=True, vals=E["lifecycle_stage"]),
    c("first_paid_at", "TIMESTAMP", "First successful paid charge; NULL if never paid."),
    c("churned_at", "TIMESTAMP", "When paid subscription ended; NULL if not churned.", p="B1"),
]))

T.append(Table("users", "main", "one row per person in a workspace",
    "Individual users belonging to an account.", "~120,000", 2, [
    c("user_id", "BIGINT", "Primary key.", pk=True),
    c("account_id", "BIGINT", "Workspace the user belongs to.", fk="accounts.account_id", req=True),
    c("email", "VARCHAR", "Synthetic email address.", req=True),
    c("role", "VARCHAR", "Workspace role.", req=True, vals=E["role"]),
    c("created_at", "TIMESTAMP", "When the user joined (UTC).", req=True),
    c("invited_by_user_id", "BIGINT", "Inviter, if the user joined via invite.", fk="users.user_id", p="P1"),
    c("first_platform", "VARCHAR", "Platform of first session.", vals=E["platform"], p="P4"),
    c("is_sso_provisioned", "BOOLEAN", "Created automatically by SSO/SCIM.", req=True, p="B3"),
    c("is_active", "BOOLEAN", "Not deactivated as of snapshot date.", req=True),
    c("deactivated_at", "TIMESTAMP", "Deactivation time, if any."),
    c("last_active_at", "TIMESTAMP", "Last event timestamp seen."),
]))

T.append(Table("events", "main", "one row per product event",
    "Raw product analytics event stream (web, iOS, Android).", "~3.5M", 2, [
    c("event_id", "BIGINT", "Primary key.", pk=True),
    c("event_ts", "TIMESTAMP", "When the event occurred (documented as UTC).", req=True, p="B5"),
    c("ingested_at", "TIMESTAMP", "When the event reached the warehouse."),
    c("user_id", "BIGINT", "Acting user.", fk="users.user_id", req=True),
    c("account_id", "BIGINT", "Workspace of the acting user.", fk="accounts.account_id", req=True),
    c("event_name", "VARCHAR", "Event type.", req=True, vals=E["event_name"], p="P1,P5"),
    c("platform", "VARCHAR", "Client platform.", req=True, vals=E["platform"], p="P4,P5"),
    c("app_version", "VARCHAR", "Client app version.", vals="semver, e.g. 4.1.3", p="P5"),
    c("session_id", "VARCHAR", "Client session identifier."),
    c("project_id", "BIGINT", "Project touched, if applicable."),
    c("task_id", "BIGINT", "Task touched, if applicable.", p="P5"),
    c("properties", "VARCHAR", "JSON string of extra properties."),
]))

T.append(Table("subscriptions", "main", "one row per paid subscription lifecycle",
    "A paid subscription (current state). Free usage has no subscription row. "
    "Change history lives in plan_changes.", "~4,600", 2, [
    c("subscription_id", "BIGINT", "Primary key.", pk=True),
    c("account_id", "BIGINT", "Owning account.", fk="accounts.account_id", req=True),
    c("plan", "VARCHAR", "Current plan.", req=True, vals=["pro", "business"]),
    c("billing_interval", "VARCHAR", "Billing cadence.", req=True, vals=E["billing_interval"]),
    c("seats", "INTEGER", "Seats currently purchased.", req=True, p="B3"),
    c("price_per_seat_usd", "DECIMAL(8,2)", "Effective USD price per seat per month after interval discount.", req=True, p="B6"),
    c("mrr_usd", "DECIMAL(12,2)", "Current normalized monthly recurring revenue (USD). 0 if canceled.", req=True, p="B1,B2"),
    c("status", "VARCHAR", "Subscription state.", req=True, vals=E["subscription_status"], p="B1"),
    c("started_at", "TIMESTAMP", "Subscription start (UTC).", req=True),
    c("current_period_start", "DATE", "Start of the current billing period."),
    c("current_period_end", "DATE", "End of the current billing period."),
    c("canceled_at", "TIMESTAMP", "Cancellation time, if canceled.", p="B1"),
    c("cancellation_source", "VARCHAR", "Who/what ended it.", vals=E["cancellation_source"], p="B1"),
    c("cancel_reason_self_reported", "VARCHAR", "Free-text/menu reason given at cancel; often missing or vague."),
]))

T.append(Table("plan_changes", "main", "one row per subscription change",
    "History of upgrades, downgrades, seat changes, interval switches, cancels, reactivations.", "~9,000", 2, [
    c("plan_change_id", "BIGINT", "Primary key.", pk=True),
    c("subscription_id", "BIGINT", "Subscription changed.", fk="subscriptions.subscription_id", req=True),
    c("account_id", "BIGINT", "Owning account.", fk="accounts.account_id", req=True),
    c("changed_at", "TIMESTAMP", "Change time (UTC).", req=True),
    c("change_type", "VARCHAR", "Kind of change.", req=True, vals=E["plan_change_type"]),
    c("from_plan", "VARCHAR", "Plan before (NULL for first paid start).", vals=E["plan"]),
    c("to_plan", "VARCHAR", "Plan after.", vals=E["plan"]),
    c("from_interval", "VARCHAR", "Interval before.", vals=E["billing_interval"]),
    c("to_interval", "VARCHAR", "Interval after.", vals=E["billing_interval"]),
    c("from_seats", "INTEGER", "Seats before."),
    c("to_seats", "INTEGER", "Seats after."),
    c("mrr_before_usd", "DECIMAL(12,2)", "MRR before change (USD)."),
    c("mrr_after_usd", "DECIMAL(12,2)", "MRR after change (USD)."),
    c("initiated_by", "VARCHAR", "Who made the change.", vals=E["initiated_by"]),
]))

# ============================ BILLING (Stage 3) ==============================
T.append(Table("invoices", "main", "one row per invoice",
    "Invoices issued to paid subscriptions.", "~45,000", 3, [
    c("invoice_id", "BIGINT", "Primary key.", pk=True),
    c("invoice_number", "VARCHAR", "Human-readable number, e.g. FD-2024-001234.", req=True),
    c("subscription_id", "BIGINT", "Subscription billed.", fk="subscriptions.subscription_id", req=True),
    c("account_id", "BIGINT", "Account billed.", fk="accounts.account_id", req=True),
    c("issued_at", "TIMESTAMP", "Issue time.", req=True, p="B5"),
    c("due_at", "TIMESTAMP", "Payment due time."),
    c("period_start", "DATE", "Service period start.", req=True),
    c("period_end", "DATE", "Service period end.", req=True),
    c("billing_reason", "VARCHAR", "Why the invoice was created.", vals=E["billing_reason"]),
    c("seats_billed", "INTEGER", "Seats charged on this invoice.", req=True, p="B3"),
    c("currency", "VARCHAR", "Invoice currency.", req=True, vals=E["currency"], p="B5"),
    c("unit_price", "DECIMAL(10,2)", "Price per seat per month in invoice currency.", p="B6"),
    c("subtotal", "DECIMAL(12,2)", "Before discount and tax, in invoice currency.", req=True),
    c("discount_amount", "DECIMAL(12,2)", "Coupon discount applied.", req=True, p="B2"),
    c("tax_amount", "DECIMAL(12,2)", "Tax, in invoice currency.", req=True),
    c("total_amount", "DECIMAL(12,2)", "Amount due, in invoice currency.", req=True, p="B2,B5,B6"),
    c("fx_rate_to_usd", "DOUBLE", "Rate used to convert to USD; may be missing.", p="B5"),
    c("total_usd", "DECIMAL(12,2)", "total_amount converted to USD; may be missing.", p="B5"),
    c("coupon_redemption_id", "BIGINT", "Redemption applied, if any.", fk="coupon_redemptions.redemption_id", p="B2"),
    c("status", "VARCHAR", "Invoice state.", req=True, vals=E["invoice_status"], p="B1"),
]))

T.append(Table("payments", "main", "one row per payment attempt",
    "Each charge attempt against an invoice, including dunning retries.", "~48,000", 3, [
    c("payment_id", "BIGINT", "Primary key.", pk=True),
    c("invoice_id", "BIGINT", "Invoice being paid.", fk="invoices.invoice_id", req=True),
    c("account_id", "BIGINT", "Paying account.", fk="accounts.account_id", req=True),
    c("attempt_number", "SMALLINT", "1 = first try; 2-4 = retries.", req=True, p="B1"),
    c("attempted_at", "TIMESTAMP", "Attempt time.", req=True, p="B1,B5"),
    c("amount", "DECIMAL(12,2)", "Amount attempted, in `currency`.", req=True),
    c("currency", "VARCHAR", "Payment currency.", req=True, vals=E["currency"], p="B5"),
    c("status", "VARCHAR", "Outcome.", req=True, vals=E["payment_status"], p="B1"),
    c("failure_code", "VARCHAR", "Reason for failure.", vals=E["failure_code"]),
    c("payment_method", "VARCHAR", "Method used.", vals=E["payment_method"]),
    c("processor_ref", "VARCHAR", "Payment processor reference."),
]))

T.append(Table("refunds", "main", "one row per refund",
    "Refunds issued against payments.", "~650", 3, [
    c("refund_id", "BIGINT", "Primary key.", pk=True),
    c("payment_id", "BIGINT", "Payment refunded.", fk="payments.payment_id", req=True, p="B7"),
    c("invoice_id", "BIGINT", "Invoice refunded.", fk="invoices.invoice_id", req=True),
    c("account_id", "BIGINT", "Account refunded.", fk="accounts.account_id", req=True),
    c("refunded_at", "TIMESTAMP", "Refund time.", req=True, p="B7"),
    c("amount", "DECIMAL(12,2)", "Refund amount, in `currency`.", req=True, p="B7"),
    c("currency", "VARCHAR", "Refund currency.", req=True, vals=E["currency"]),
    c("reason", "VARCHAR", "Refund reason.", vals=E["refund_reason"]),
    c("status", "VARCHAR", "Refund state.", req=True, vals=E["refund_status"]),
    c("issued_by", "VARCHAR", "Support agent id or 'system'.", p="B7"),
    c("processor_refund_id", "VARCHAR", "Processor reference.", p="B7"),
]))

T.append(Table("coupons", "main", "one row per coupon code",
    "Discount codes created by marketing, sales and support.", "~25", 3, [
    c("coupon_id", "BIGINT", "Primary key.", pk=True),
    c("code", "VARCHAR", "Redemption code.", req=True),
    c("campaign", "VARCHAR", "Campaign the coupon belongs to."),
    c("discount_type", "VARCHAR", "Percent or fixed amount.", req=True, vals=E["discount_type"]),
    c("percent_off", "DOUBLE", "Percent off (0-100) if percent type."),
    c("amount_off_usd", "DECIMAL(10,2)", "Amount off per invoice if fixed type."),
    c("duration", "VARCHAR", "How long the discount lasts.", req=True, vals=E["coupon_duration"]),
    c("duration_months", "INTEGER", "Months, if duration = repeating."),
    c("stackable", "BOOLEAN", "Whether it may combine with other coupons.", req=True, p="B2"),
    c("max_redemptions", "INTEGER", "Redemption cap, if any."),
    c("valid_from", "DATE", "First valid day.", req=True),
    c("valid_to", "DATE", "Last valid day."),
]))

T.append(Table("coupon_redemptions", "main", "one row per coupon use",
    "An account redeeming a coupon on a subscription.", "~1,300", 3, [
    c("redemption_id", "BIGINT", "Primary key.", pk=True),
    c("coupon_id", "BIGINT", "Coupon used.", fk="coupons.coupon_id", req=True),
    c("account_id", "BIGINT", "Account redeeming.", fk="accounts.account_id", req=True, p="B2"),
    c("subscription_id", "BIGINT", "Subscription discounted.", fk="subscriptions.subscription_id", req=True),
    c("redeemed_at", "TIMESTAMP", "Redemption time.", req=True, p="B2"),
    c("discount_ends_at", "TIMESTAMP", "When the discount lapses; NULL if forever."),
    c("redemption_channel", "VARCHAR", "Where it was applied.", vals=E["redemption_channel"]),
]))

T.append(Table("seat_usage_monthly", "main", "one row per account per month",
    "Month-end seat counts: billed vs provisioned vs active.", "~300,000", 3, [
    c("account_id", "BIGINT", "Account.", fk="accounts.account_id", req=True),
    c("month_start", "DATE", "First day of the month.", req=True),
    c("plan", "VARCHAR", "Plan at month end.", vals=E["plan"]),
    c("seats_billed", "INTEGER", "Seats on the paid subscription (0 for free).", req=True, p="B3"),
    c("seats_provisioned", "INTEGER", "Seats existing in the workspace.", req=True, p="B3"),
    c("seats_sso_provisioned", "INTEGER", "Of provisioned, created via SSO/SCIM.", req=True, p="B3"),
    c("seats_active", "INTEGER", "Seats with at least one event in the month.", req=True),
], composite_pk=("account_id", "month_start")))

# ============================ GROWTH (Stage 4) ===============================
T.append(Table("experiments", "main", "one row per A/B test",
    "Registry of product experiments.", "~6", 4, [
    c("experiment_id", "BIGINT", "Primary key.", pk=True),
    c("name", "VARCHAR", "Short name.", req=True),
    c("hypothesis", "VARCHAR", "What the team expected."),
    c("unit_type", "VARCHAR", "Randomization unit.", req=True, vals=E["experiment_unit"]),
    c("surface", "VARCHAR", "Product area tested."),
    c("primary_metric", "VARCHAR", "Decision metric.", req=True),
    c("planned_treatment_share", "DOUBLE", "Intended share assigned to treatment.", req=True, p="P2"),
    c("start_date", "DATE", "Start date.", req=True, p="P3"),
    c("end_date", "DATE", "End date."),
    c("status", "VARCHAR", "Experiment state.", req=True, vals=E["experiment_status"]),
    c("owner", "VARCHAR", "Owning PM/analyst."),
]))

T.append(Table("experiment_assignments", "main", "one row per unit per experiment",
    "Who was assigned to which variant.", "~60,000", 4, [
    c("assignment_id", "BIGINT", "Primary key.", pk=True),
    c("experiment_id", "BIGINT", "Experiment.", fk="experiments.experiment_id", req=True),
    c("unit_id", "BIGINT", "user_id or account_id, per experiments.unit_type.", req=True),
    c("variant", "VARCHAR", "Assigned variant.", req=True, vals=E["variant"], p="P2"),
    c("assigned_at", "TIMESTAMP", "Assignment time (UTC).", req=True, p="P3"),
    c("platform", "VARCHAR", "Platform at assignment.", vals=E["platform"], p="P4"),
    c("first_exposed_at", "TIMESTAMP", "First time the variant was shown; NULL if never exposed."),
]))

T.append(Table("marketing_spend", "main", "one row per day per channel per campaign",
    "Paid media spend as booked by the marketing team.", "~13,000", 4, [
    c("spend_id", "BIGINT", "Primary key.", pk=True),
    c("spend_date", "DATE", "Day of spend.", req=True),
    c("channel", "VARCHAR", "Paid channel.", req=True, vals=E["paid_channel"], p="G2"),
    c("campaign", "VARCHAR", "Campaign name.", req=True, p="G1"),
    c("impressions", "BIGINT", "Impressions served."),
    c("clicks", "BIGINT", "Clicks."),
    c("spend_amount", "DECIMAL(12,2)", "Spend in `currency`.", req=True, p="B5"),
    c("currency", "VARCHAR", "Spend currency.", req=True, vals=E["currency"], p="B5"),
    c("spend_usd", "DECIMAL(12,2)", "USD equivalent; may be missing.", p="B5"),
]))

T.append(Table("platform_reported_conversions", "main", "one row per day per platform campaign",
    "Conversions as claimed by ad platforms (their attribution, not ours).", "~13,000", 4, [
    c("report_id", "BIGINT", "Primary key.", pk=True),
    c("report_date", "DATE", "Day reported.", req=True),
    c("channel", "VARCHAR", "Ad platform channel.", req=True, vals=E["paid_channel"], p="G1"),
    c("campaign", "VARCHAR", "Campaign name.", req=True),
    c("attribution_model", "VARCHAR", "Platform attribution setting.", vals=E["attribution_model"], p="G1"),
    c("platform_signups", "INTEGER", "Signups the platform claims.", req=True, p="G1"),
    c("platform_paid_conversions", "INTEGER", "Paid conversions the platform claims.", req=True, p="G1"),
    c("platform_revenue_usd", "DECIMAL(12,2)", "Revenue the platform claims.", p="G1"),
]))

T.append(Table("leads", "main", "one row per sales/marketing lead",
    "CRM lead records (sales-assisted funnel and inbound demo requests).", "~6,500", 4, [
    c("lead_id", "BIGINT", "Primary key.", pk=True),
    c("created_at", "TIMESTAMP", "Lead creation (UTC).", req=True),
    c("company_name", "VARCHAR", "Company on the lead."),
    c("email_domain", "VARCHAR", "Contact email domain."),
    c("company_size_band", "VARCHAR", "Company size.", vals=E["company_size_band"]),
    c("lead_source", "VARCHAR", "Raw CRM source label; not normalized.", p="G4"),
    c("lead_status", "VARCHAR", "Current funnel stage.", req=True, vals=E["lead_status"]),
    c("owner_rep_id", "INTEGER", "Assigned sales rep."),
    c("mql_at", "TIMESTAMP", "Became MQL."),
    c("sql_at", "TIMESTAMP", "Became SQL."),
    c("opportunity_at", "TIMESTAMP", "Opportunity created."),
    c("closed_at", "TIMESTAMP", "Won or lost date."),
    c("deal_arr_usd", "DECIMAL(12,2)", "Contracted ARR if won.", p="G3"),
    c("loss_reason", "VARCHAR", "Reason if lost."),
    c("account_id", "BIGINT", "Account created from the lead, if any.", fk="accounts.account_id"),
]))

T.append(Table("sales_touches", "main", "one row per rep interaction",
    "Calls, emails and demos logged by sales reps.", "~30,000", 4, [
    c("touch_id", "BIGINT", "Primary key.", pk=True),
    c("lead_id", "BIGINT", "Lead touched.", fk="leads.lead_id", req=True),
    c("account_id", "BIGINT", "Account touched, if linked.", fk="accounts.account_id"),
    c("rep_id", "INTEGER", "Sales rep.", req=True),
    c("touched_at", "TIMESTAMP", "Interaction time (UTC).", req=True),
    c("touch_type", "VARCHAR", "Kind of touch.", req=True, vals=E["touch_type"]),
    c("outcome", "VARCHAR", "Result.", vals=E["touch_outcome"]),
    c("duration_minutes", "INTEGER", "Length for calls/demos."),
]))

# ============================ HIDDEN _truth (Stage 5) ========================
T.append(Table("true_churn_reason", "_truth", "one row per churned account",
    "Ground-truth reason each account really churned.", "~1,000", 5, [
    c("account_id", "BIGINT", "Churned account.", pk=True, fk="accounts.account_id"),
    c("churned_at", "TIMESTAMP", "True churn time."),
    c("true_reason", "VARCHAR", "Generated cause.", vals="price | missing_feature | low_adoption | payment_failure | competitor | team_shrunk | project_ended"),
    c("is_involuntary", "BOOLEAN", "Churned because payment never recovered."),
    c("preventable", "BOOLEAN", "Would a working process have saved it?"),
    c("planted_problem_id", "VARCHAR", "B-code if caused by a planted problem."),
]))

T.append(Table("true_user_segment", "_truth", "one row per user",
    "Latent behavior assigned at generation time.", "~120,000", 5, [
    c("user_id", "BIGINT", "User.", pk=True, fk="users.user_id"),
    c("account_id", "BIGINT", "Account.", fk="accounts.account_id"),
    c("latent_engagement", "DOUBLE", "Latent engagement score driving event rates (0-1)."),
    c("true_segment", "VARCHAR", "Archetype.", vals="power | core | casual | dormant"),
    c("will_activate", "BOOLEAN", "Generated to hit activation within 7 days."),
    c("aha_invited_3d", "BOOLEAN", "Generated to invite a teammate within 3 days."),
    c("retained_12w", "BOOLEAN", "Generated 12-week retention outcome."),
]))

T.append(Table("true_experiment_effect", "_truth", "one row per experiment x platform x week",
    "True causal effect injected into each experiment.", "~100", 5, [
    c("effect_id", "BIGINT", "Primary key.", pk=True),
    c("experiment_id", "BIGINT", "Experiment.", fk="experiments.experiment_id", req=True),
    c("platform", "VARCHAR", "Platform slice; 'all' for overall.", req=True),
    c("week_since_start", "INTEGER", "0-based week of the test.", req=True),
    c("true_effect_pp", "DOUBLE", "True lift on the primary metric, percentage points."),
    c("effect_shape", "VARCHAR", "constant | decaying | negative_on_slice"),
    c("note", "VARCHAR", "Plain-English description."),
]))

T.append(Table("answer_key", "_truth", "one row per planted problem",
    "The grader's sheet: what was planted, how big, how to find and fix it.", "16", 5, [
    c("problem_id", "VARCHAR", "B1..B7, P1..P5, G1..G4.", pk=True),
    c("category", "VARCHAR", "billing | product | growth", req=True),
    c("title", "VARCHAR", "Short name.", req=True),
    c("description", "VARCHAR", "What was planted."),
    c("affected_tables", "VARCHAR", "Comma-separated tables."),
    c("affected_row_count", "BIGINT", "Rows/accounts/users affected."),
    c("affected_arr_usd", "DECIMAL(12,2)", "ARR impact where applicable."),
    c("naive_metric", "VARCHAR", "Metric an unaware analyst would report."),
    c("naive_value", "DOUBLE", "Its (wrong) value."),
    c("true_value", "DOUBLE", "Corrected value."),
    c("detection_hint", "VARCHAR", "How a good analyst would find it."),
    c("correct_fix", "VARCHAR", "How to correct for it."),
]))

T.append(Table("planted_rows", "_truth", "one row per affected record",
    "Row-level flags so every planted problem can be verified exactly.", "~5,000", 5, [
    c("problem_id", "VARCHAR", "Problem code.", req=True, fk="answer_key.problem_id"),
    c("table_name", "VARCHAR", "Affected table.", req=True),
    c("pk_value", "VARCHAR", "Primary key value of the affected row (as text).", req=True),
    c("role", "VARCHAR", "e.g. 'duplicate', 'original', 'affected'."),
], composite_pk=("problem_id", "table_name", "pk_value")))

TABLES = T
PUBLIC = [t for t in T if t.schema == "main"]
HIDDEN = [t for t in T if t.schema == "_truth"]
ALL_PROBLEMS = (["B%d" % i for i in range(1, 8)] + ["P%d" % i for i in range(1, 6)]
                + ["G%d" % i for i in range(1, 5)])
