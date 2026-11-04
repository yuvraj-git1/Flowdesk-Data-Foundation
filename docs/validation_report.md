# Validation report (pandas mirror of load_duckdb.py checks)

| Metric | Observed | Target |
|---|---|---|
| Signups (incl. dups/test) | 39974 | ~40K |
| Ever-paid accounts | 4091 | ~4K |
| Active paid at end | 2506 | ~2.8K |
| ARR at end ($) | 5908118 | ~6M |
| Sales-assisted share of paid | 0.142 | ~0.15 |
| Events | 3450412 | 3-4M |
| First-attempt payment failure | 0.0414 | ~0.04 |
| MRR growth 2024 / 2025 (x) | 2.51 / 1.13 | strong / stalled |
| Owner activation (7d) | 0.414 | - |
| Owner aha share | 0.271 | - |
| 12w retention aha / non-aha | 0.545 / 0.226 | ~0.55 / ~0.20 |
| Distinct signup_source labels | 46 | messy (~15%) |

## Planted problems: key vs measured

| ID | Title | Rows | ARR/$ | Naive | True |
|---|---|---|---|---|---|
| B1 | Dunning outage (Feb-Jun 2025) | 313 | 446,717 | 0.000 | 0.636 |
| B2 | Coupon stacking (Sep 2024-Jan 2025) | 140 | 187,798 | 319,478.400 | 131,680.800 |
| B3 | Unbilled SSO seats | 60 | 218,592 | 218,188.800 | 436,780.800 |
| B4 | Duplicate accounts | 974 | 0 | 39,974.000 | 39,000.000 |
| B5 | Currency and timezone mess | 2220 | 0 | 6,966,441.550 | 5,361,520.759 |
| B6 | Pricing bug (Mar 3-9 2025) | 25 | 6,149 | 6,149.270 | 12,298.540 |
| B7 | Duplicate refunds | 5 | 797 | 714.000 | 709.000 |
| P1 | Aha moment: teammate invite within 3 days | 9576 | 0 | 0.279 | 0.532 |
| P2 | Sample ratio mismatch (pricing_page_redesign) | 1591 | 0 | 0.471 | 0.500 |
| P3 | Novelty effect (onboarding_checklist) | 3538 | 0 | 4.977 | 0.000 |
| P4 | Mobile harmed by treatment (new_onboarding_flow) | 4841 | 0 | 2.120 | -7.000 |
| P5 | Android v4.2.1 task_completed double-firing | 2364 | 0 | 2,364.000 | 0.000 |
| G1 | Attribution overlap | 0 | 0 | 1.730 | 1.000 |
| G2 | Cheap-but-bad review-site channel | 3164 | 0 | 19.291 | 1,130.307 |
| G3 | Sales-assisted LTV ~3x | 920 | 0 | 1.000 | 2.714 |
| G4 | Messy channel labels | 5957 | 0 | 0.149 | 0.000 |
