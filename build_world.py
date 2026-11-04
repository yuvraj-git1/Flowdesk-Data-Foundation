"""Stages 4-7 driver: python build_world.py  -> data/csv/*.csv (+ parquet if pyarrow), docs/validation_report.md"""
import json, numpy as np, pandas as pd
from world_b import *
from world_b import T0, TEND

TS = lambda s: pd.Series(pd.Timestamp('2023-01-01') + pd.to_timedelta(pd.Series(s, dtype='float64').values, unit='s'))
TBL = {t.name: t for t in TABLES}

def fin(d, name):
    t = TBL[name]; d = d.reset_index(drop=True); out = {}
    for c in t.cols:
        x = d[c.name]
        if c.dtype in ('BIGINT', 'INTEGER', 'SMALLINT'): x = pd.to_numeric(x).astype('Int64')
        elif c.dtype == 'DOUBLE': x = pd.to_numeric(x).astype(float)
        elif c.dtype.startswith('DECIMAL'): x = pd.to_numeric(x).astype(float).round(2)
        elif c.dtype == 'BOOLEAN': x = x.astype('boolean')
        elif c.dtype == 'DATE': x = pd.to_datetime(x).dt.strftime('%Y-%m-%d')
        out[c.name] = x
    return pd.DataFrame(out)

def save(d, name):
    d.to_csv(f'{OUT}/csv/{name}.csv', index=False, date_format='%Y-%m-%d %H:%M:%S')
    try: d.to_parquet(f'{OUT}/{name}.parquet', index=False)
    except Exception: pass
    return len(d)

R = {}   # name -> df
# ---------------- accounts
fp_ = A.first_paid.values
acc = pd.DataFrame(dict(account_id=aid, created_at=TS(cre), company_name=A.name.values, email_domain=A.domain.values, industry=A.industry.values, company_size_band=np.array(ENUMS['company_size_band'])[A['size'].values],
    country=A.country.values, billing_currency=A.currency.values, timezone=A.tz.values, signup_source=A.signup_source.values, utm_source=A.utm_source.values, utm_medium=A.utm_medium.values,
    utm_campaign=A.utm_campaign.values, acquisition_motion=A.motion.values, lead_id=A.lead_id.values, owner_user_id=owner_uid, sso_enabled=sso,
    lifecycle_stage=np.where(~paid_a, 'free', np.where(np.array([end_status.get(i) == 'canceled' for i in range(N)]), 'churned', 'paid')), first_paid_at=TS(fp_),
    churned_at=TS(np.where(churn_a < 10 ** 9, churn_a, np.nan))))
R['accounts'] = acc
R['users'] = users
subs['canceled_at'] = TS(subs.canceled_at.values)
for c_ in ('started_at',): subs[c_] = TS(subs[c_].values)
for c_ in ('current_period_start', 'current_period_end'): subs[c_] = TS(subs[c_].values).dt.normalize()
R['subscriptions'] = subs
pc = pc.sort_values('changed_at', kind='stable').reset_index(drop=True); pc['plan_change_id'] = np.arange(1, len(pc) + 1); pc['changed_at'] = TS(pc.changed_at.values)
R['plan_changes'] = pc
inv['issued_at_f'] = TS(inv.issued_at.values); inv['due_at_f'] = TS(inv.due_at.values)
iv = inv.assign(issued_at=inv.issued_at_f, due_at=inv.due_at_f, period_start=TS(inv.period_start.values).dt.normalize(), period_end=TS(inv.period_end.values).dt.normalize(),
                invoice_number=[f"FD-{2023 + int(s // (365.25 * DAY))}-{i:06d}" for s, i in zip(inv.issued_at_utc, inv.invoice_id)])
R['invoices'] = iv
pay['attempted_at'] = TS(pay.attempted_at.values); R['payments'] = pay
refunds['refunded_at'] = TS(refunds.refunded_at.values); R['refunds'] = refunds
cpn = coupons.copy(); R['coupons'] = cpn
red['discount_ends_at'] = TS(red.ends.astype(float).values); red['redeemed_at'] = TS(red.redeemed_at.values); R['coupon_redemptions'] = red

# ---------------- seat_usage_monthly
P = pd.DataFrame(O['seat'], columns=['ai', 'ms', 'plan', 'seats_billed']); P['account_id'] = aid[P.ai.values]; P['mon'] = ts(P.ms.values).astype('datetime64[M]').astype('int64')
P = P.drop_duplicates(['account_id', 'mon'], keep='last')[['account_id', 'mon', 'plan', 'seats_billed']]
ea = pd.DataFrame(dict(account_id=acct_of_u[eu - 1].astype(np.int32), mon=ts(et_u).astype('datetime64[M]').astype('int64').astype(np.int32), u=eu)).drop_duplicates()
G = ea.groupby(['account_id', 'mon']).size().rename('seats_active').reset_index(); del ea
S_ = P.merge(G, on=['account_id', 'mon'], how='outer'); S_['plan'] = S_.plan.fillna('free'); S_['seats_billed'] = S_.seats_billed.fillna(0).astype(int); S_['seats_active'] = S_.seats_active.fillna(0).astype(int)
uc = pd.DataFrame(dict(account_id=aid[ai][pos < 99], mon=ts(created[pos < 99]).astype('datetime64[M]').astype('int64'))).groupby(['account_id', 'mon']).size()
uc = uc.groupby(level=0).cumsum().rename('cum').reset_index().sort_values('mon')
S_ = pd.merge_asof(S_.sort_values('mon'), uc, on='mon', by='account_id', direction='backward'); S_['cum'] = S_.cum.fillna(1)
ub = pd.Series(unbilled, index=aid); smon = pd.Series(ts(np.where(start_a >= 0, start_a + 30 * DAY, 0)).astype('datetime64[M]').astype('int64'), index=aid)
extra = np.where(S_.mon.values >= S_.account_id.map(smon).values, S_.account_id.map(ub).values, 0) * (S_.seats_billed > 0)
S_['seats_provisioned'] = np.where(S_.seats_billed > 0, S_.seats_billed + extra, np.minimum(5, S_.cum)).astype(int)
sso_s = pd.Series(sso, index=aid); S_['seats_sso_provisioned'] = np.where((S_.seats_billed > 0) & S_.account_id.map(sso_s).values, S_.seats_provisioned, 0)
S_['seats_active'] = np.minimum(S_.seats_active, S_.seats_provisioned); S_['month_start'] = S_.mon.values.astype('int64').astype('datetime64[M]').astype('datetime64[D]')
R['seat_usage_monthly'] = S_.sort_values(['account_id', 'mon'])

# ---------------- experiments
EX = [(1, 'onboarding_checklist', 'A guided checklist raises 7-day activation', 'user', 'onboarding', 'activation_7d'), (2, 'new_onboarding_flow', 'Streamlined first-run flow raises activation', 'user', 'onboarding', 'activation_7d'),
      (3, 'pricing_page_redesign', 'Clearer pricing page lifts paid conversion', 'account', 'pricing', 'paid_conversion_30d'), (4, 'invite_prompt', 'Prompt to invite a teammate raises early invites', 'user', 'onboarding', 'teammate_invited_3d'),
      (5, 'annual_discount_banner', 'Annual-savings banner shifts mix to annual', 'account', 'checkout', 'annual_share'), (6, 'dark_mode_default', 'Dark mode default improves engagement', 'user', 'settings', 'activation_7d')]
R['experiments'] = pd.DataFrame(dict(experiment_id=[x[0] for x in EX], name=[x[1] for x in EX], hypothesis=[x[2] for x in EX], unit_type=[x[3] for x in EX], surface=[x[4] for x in EX],
    primary_metric=[x[5] for x in EX], planned_treatment_share=.5, start_date=[EXP[x[0]][0] for x in EX], end_date=[EXP[x[0]][1] for x in EX], status='completed', owner=['pm_ava', 'pm_ava', 'pm_ravi', 'pm_li', 'pm_ravi', 'pm_li']))
rows = [(k, u, v, c_, p_) for k, u, v, c_, p_ in asg]
for k, mk_, trt in ((3, m3, treat3), (5, m5, treat5)):
    for i in np.where(mk_)[0]: rows.append((k, aid[i], 'treatment' if trt[i] else 'control', cre[i], plat[np.where((ai == i) & (pos == 0))[0][0]]))
asn = pd.DataFrame(rows, columns=['experiment_id', 'unit_id', 'variant', 'c', 'p']); asn = asn.sort_values(['c', 'experiment_id'], kind='stable').reset_index(drop=True)
asn['assignment_id'] = np.arange(1, len(asn) + 1); asn['assigned_at'] = TS(asn.c.values + 60); asn['platform'] = np.array(ENUMS['platform'])[asn.p.values.astype(int)]
asn['first_exposed_at'] = TS(np.where(r2.random(len(asn)) < .03, np.nan, asn.c.values + 60 + r2.uniform(0, DAY, len(asn)))); R['experiment_assignments'] = asn
mkt['spend_date'] = pd.to_datetime(mkt.spend_date); R['marketing_spend'] = mkt
plat_rep['report_date'] = pd.to_datetime(plat_rep.report_date); R['platform_reported_conversions'] = plat_rep
leads['created_at'] = TS(leads.created_at.values)
for c_ in ('mql_at', 'sql_at', 'opportunity_at', 'closed_at'): leads[c_] = TS(np.where(leads[c_].values > 0, leads[c_].values, np.nan))
leads['account_id'] = [aid[int(a)] if a >= 0 else None for a in leads.acct]; R['leads'] = leads
touches['touched_at'] = TS(touches.touched_at.values); R['sales_touches'] = touches

# ---------------- _truth
tcr = chd.assign(account_id=aid[chd.a.values], churned_at=TS(chd.t.values), is_involuntary=chd.invol, true_reason=tc.true_reason.values,
    preventable=(chd.invol & chd.rw) | (tc.true_reason.values == 'low_adoption') & (r2.random(len(chd)) < .3), planted_problem_id=np.where(chd.b1, 'B1', None))
R['true_churn_reason'] = tcr
seg = np.select([e_u > .75, e_u > .5, e_u > .25], ['power', 'core', 'casual'], 'dormant')
R['true_user_segment'] = pd.DataFrame(dict(user_id=uid, account_id=aid[ai], latent_engagement=e_u.round(4), true_segment=seg, will_activate=will, aha_invited_3d=aha_u, retained_12w=pd.array(np.where(mature, ret, pd.NA), dtype='boolean')))
te = []
for wk in range(6): te.append((1, 'all', wk, [14, 10, 5, 1, 0, 0][wk], 'decaying', 'novelty effect: lift fades by week 4'))
for p_, v_ in (('web', 8), ('ios', -7), ('android', -7)):
    for wk in range(6): te.append((2, p_, wk, v_, 'constant' if v_ > 0 else 'negative_on_slice', 'helps web, hurts mobile'))
te += [(3, 'all', wk, 3.0, 'constant', 'conversion lift') for wk in range(6)] + [(4, 'all', wk, 6.0, 'constant', 'aha rate lift (owners)') for wk in range(6)]
te += [(5, 'all', wk, 12.0, 'constant', 'annual-mix lift') for wk in range(6)] + [(6, 'all', wk, 0.0, 'constant', 'null experiment') for wk in range(6)]
R['true_experiment_effect'] = pd.DataFrame(te, columns=['experiment_id', 'platform', 'week_since_start', 'true_effect_pp', 'effect_shape', 'note']).assign(effect_id=lambda d: np.arange(1, len(d) + 1))

# ---------------- answer key + planted_rows
prow = []
add = lambda p, t, ids, role: prow.extend((p, t, str(i), role) for i in ids)
b1s = chd[chd.b1]; add('B1', 'subscriptions', b1s.sid, 'affected')
st2 = [j + 1 for j in stackset]; add('B2', 'subscriptions', st2, 'affected'); add('B2', 'coupon_redemptions', red[red.subscription_id.isin(st2)].redemption_id, 'stacked_redemption')
add('B3', 'accounts', aid[b3], 'unbilled_sso'); add('B4', 'accounts', aid[kind == 'dup'], 'duplicate'); add('B4', 'accounts', aid[A.oi.values[kind == 'dup']], 'original')
add('B5', 'invoices', inv.invoice_id[b5a], 'missing_fx'); add('B5', 'invoices', inv.invoice_id[b5b], 'unconverted_usd'); add('B6', 'invoices', inv.invoice_id[inv.index.isin(b6)], 'underbilled')
add('B7', 'refunds', refunds.refund_id[refunds.dup], 'duplicate'); add('P5', 'events', eid[is_dup], 'duplicate'); add('G4', 'accounts', aid[messy], 'messy_label')
planted = pd.DataFrame(prow, columns=['problem_id', 'table_name', 'pk_value', 'role']); R['planted_rows'] = planted

fc = pay[pay.attempt_number == 1].merge(inv[['invoice_id', 'issued_at_utc']], on='invoice_id'); fc = fc[fc.status == 'failed']
okinv = set(pay.loc[pay.status == 'succeeded', 'invoice_id']); fc['rec'] = fc.invoice_id.isin(okinv); fc['win'] = (fc.issued_at_utc >= B1W[0]) & (fc.issued_at_utc < B1W[1])
r_win, r_base = fc[fc.win].rec.mean(), fc[~fc.win].rec.mean()
unb_arr = float((unbilled[b3] * 24 * 12).sum()); bill_arr = float(subs.set_index('account_idx').loc[b3, 'mrr_usd'].sum() * 12)
stk_arr = float(sum(min(.95, sum(c[2] for c in reds[j])) * arr0[ca[j]] for j in stackset)); stk_list = float(sum(arr0[ca[j]] for j in stackset))
fxt = np.array([FXB[c] for c in inv.currency]) * (1 + .03 * np.sin(inv.issued_at_utc.values / DAY / 120)); nu_ = (inv.currency != 'USD').values
nv5 = float(inv.total_usd[nu_].sum()); tv5 = float((inv.total_amount.values * fxt)[nu_].sum())
ow_m = (pos == 0) & mature; o_all = ret[ow_m].mean(); o_a = ret[ow_m & aha_u].mean(); o_n = ret[ow_m & ~aha_u].mean()
a3 = asn[asn.experiment_id == 3]; srm = (a3.variant == 'treatment').mean()
wl = pd.Series(will, index=uid); x1 = asn[asn.experiment_id == 1]; d1 = wl[x1[x1.variant == 'treatment'].unit_id].mean() - wl[x1[x1.variant == 'control'].unit_id].mean()
x2 = asn[asn.experiment_id == 2]; d2 = wl[x2[x2.variant == 'treatment'].unit_id].mean() - wl[x2[x2.variant == 'control'].unit_id].mean()
gp = plat_rep.groupby('channel')[['platform_paid_conversions']].sum().platform_paid_conversions; act_c = cvd.assign(c=A.ch.values[cvd.index]).groupby('c').size(); act_c.index = np.array(CH)[act_c.index]
g1 = float(gp['paid_social'] / act_c['paid_social']); g1b = float(gp['paid_search'] / act_c['paid_search'])
mk_usd = mkt.assign(u=mkt.spend_amount * mkt.currency.map(FXB)).groupby('channel').u.sum(); sg_ = pd.Series(ch).map(dict(enumerate(CH))).value_counts(); pc_ = cvd.assign(c=np.array(CH)[ch[cvd.index]]).groupby('c').size()
cps_r, cpa_r = float(mk_usd['review_site'] / sg_['review_site']), float(mk_usd['review_site'] / pc_['review_site']); cpa_s = float(mk_usd['paid_search'] / pc_['paid_search'])
col = pay[pay.status == 'succeeded'].assign(u=lambda d: d.amount * d.currency.map(FXB)).groupby('account_idx').u.sum()
mo = pd.Series(sales, index=range(N)); ltv_s = col[col.index.map(mo)].mean(); ltv_c = col[~col.index.map(mo)].mean(); g3 = float(ltv_s / ltv_c)
AK = [('B1', 'billing', 'Dunning outage (Feb-Jun 2025)', 'Retry attempts (days 1,3,7) stopped running; every failed first attempt in window went straight to uncollectible and the sub was canceled. affected_row_count = all accounts hit; affected_arr_usd = ARR of those that retries would have recovered.', 'payments,invoices,subscriptions', len(b1s), float(b1s[b1s.rw].arr.sum()), 'payment_recovery_rate_in_window', r_win, r_base, 'Compare recovery rate of failed first attempts by month; look for missing attempt_number 2-4', 'Exclude window from recovery benchmarks; treat canceled-by-payment_failure accounts as recoverable ARR'),
      ('B2', 'billing', 'Coupon stacking (Sep 2024-Jan 2025)', 'Non-stackable coupons redeemed 2-3x on one subscription; invoices discounted far beyond intent, while subscriptions.mrr_usd still shows list MRR.', 'coupon_redemptions,invoices,coupons', len(stackset), stk_arr, 'list_ARR_of_stacker_accounts', stk_list, stk_list - stk_arr, 'Group redemptions by subscription with overlapping validity where coupons.stackable = false', 'Report cash ARR = list ARR - discounts'),
      ('B3', 'billing', 'Unbilled SSO seats', 'SSO provisioning created seats never added to the paid seat count on ~8% of active Business accounts.', 'seat_usage_monthly,users,subscriptions', len(b3), unb_arr, 'billed_ARR_of_affected_accounts', bill_arr, bill_arr + unb_arr, 'seats_provisioned > seats_billed with seats_sso_provisioned > 0', 'Bill or true-up unbilled seats; recompute ARR'),
      ('B4', 'billing', 'Duplicate accounts', 'Owners re-signed up within 30 days under name variants (case, Inc, spacing).', 'accounts', ND, 0., 'account_count', float(N), float(N - ND), 'Normalize company_name/email_domain and look for near-identical pairs within 30 days', 'Collapse to the earliest account'),
      ('B5', 'billing', 'Currency and timezone mess', 'Non-USD invoices with missing fx/total_usd, some total_usd left unconverted; INR/EUR invoice issued_at in local time; iOS event_ts in device-local time.', 'invoices,events', int(b5a.sum() + b5b.sum()), 0., 'sum_total_usd_non_USD_invoices', nv5, tv5, 'Check fx nulls, total_usd = total_amount for non-USD, ingested_at < event_ts on iOS', 'Recompute USD from fx table; convert local stamps to UTC'),
      ('B6', 'billing', 'Pricing bug (Mar 3-9 2025)', '25 Business accounts invoiced at Pro price on one invoice. affected_arr_usd = one-time revenue lost, not ARR.', 'invoices,payments', len(b6), float(lost6), 'billed_usd_on_affected_invoices', float(inv.loc[b6, 'total_usd'].sum()), float(inv.loc[b6, 'total_usd'].sum() * 2), 'unit_price on business invoices = 12 vs subscription price 24', 'Back-bill or credit; exclude from price analysis'),
      ('B7', 'billing', 'Duplicate refunds', 'Same payment refunded twice seconds apart.', 'refunds', nd7, float(refunds[refunds.dup].amount.mul(refunds[refunds.dup].currency.map(FXB)).sum()), 'refund_count', float(len(refunds)), float(len(refunds) - nd7), 'Group by payment_id; refunds within 3 minutes', 'Dedupe on payment_id + amount'),
      ('P1', 'product', 'Aha moment: teammate invite within 3 days', 'Owners who invite a teammate within 3 days retain far better at 12 weeks.', 'events,users', int(aha[(cre < TEND - 98 * DAY)].sum()), 0., 'owner_12w_retention_overall', float(o_all), float(o_a), f'Compare 12-week retention by invite-within-3d (non-aha {o_n:.2f})', 'Optimize onboarding toward early invites'),
      ('P2', 'product', 'Sample ratio mismatch (pricing_page_redesign)', 'Planned 50/50, observed ~52.3% control / 47.7% treatment.', 'experiment_assignments', len(a3), 0., 'treatment_share', float(srm), .5, 'Chi-square on assignment counts', 'Do not trust results until the assignment bug is understood'),
      ('P3', 'product', 'Novelty effect (onboarding_checklist)', 'Lift decays from +14pp in week 0 to 0 by week 4.', 'experiment_assignments,events', len(x1), 0., 'pooled_effect_pp', float(d1 * 100), 0., 'Plot effect by week since assignment', 'Use steady-state weeks only'),
      ('P4', 'product', 'Mobile harmed by treatment (new_onboarding_flow)', 'Web +8pp, iOS/Android -7pp; pooled effect looks mildly positive.', 'experiment_assignments,events', len(x2), 0., 'pooled_effect_pp', float(d2 * 100), -7., 'Segment by platform', 'Ship to web only'),
      ('P5', 'product', 'Android v4.2.1 task_completed double-firing', 'For 3 weeks (Oct 14-Nov 3 2024), 70% of Android users fire task_completed twice; inflates activation.', 'events', int(is_dup.sum()), 0., 'duplicate_task_completed_rows', float(is_dup.sum()), 0., 'Same user/task_id/ts duplicates on android 4.2.1', 'Dedupe on (user_id, task_id, event_name)'),
      ('G1', 'growth', 'Attribution overlap', 'Ad platforms claim more paid conversions than occurred (paid_social ~1.6x, paid_search ~1.3x).', 'platform_reported_conversions,marketing_spend', 0, 0., 'paid_social_claimed_over_actual', g1, 1., 'Compare platform totals to first_paid_at by utm_campaign', f'Use first-party attribution (paid_search ratio {g1b:.2f})'),
      ('G2', 'growth', 'Cheap-but-bad review-site channel', 'Review-site signups are cheap but rarely convert and churn faster.', 'accounts,marketing_spend', int(sg_['review_site']), 0., 'cost_per_signup_review_site', cps_r, cpa_r, f'Compute cost per paid account (paid_search: {cpa_s:.0f})', 'Judge channels by cost per retained paid account'),
      ('G3', 'growth', 'Sales-assisted LTV ~3x', 'Sales-assisted accounts are bigger, annual-heavy and churn less.', 'accounts,invoices,leads', int(sales.sum()), 0., 'ltv_ratio_naive_assumed', 1., g3, 'Compare collected revenue per account by acquisition_motion', 'Do not blend motions in LTV/CAC'),
      ('G4', 'growth', 'Messy channel labels', f'~15% of signup_source/lead_source values are non-canonical variants.', 'accounts,leads', int(messy.sum()), 0., 'share_noncanonical_labels', float(messy.mean()), 0., 'SELECT DISTINCT signup_source', 'Map variants to canonical channel')]
R['answer_key'] = pd.DataFrame(AK, columns=['problem_id', 'category', 'title', 'description', 'affected_tables', 'affected_row_count', 'affected_arr_usd', 'naive_metric', 'naive_value', 'true_value', 'detection_hint', 'correct_fix'])

# ---------------- export
sizes = {}
for name, d in R.items(): sizes[name] = save(fin(d, name), name)
# events, chunked
EVT = np.array(EV); PL = np.array(ENUMS['platform']); VR = np.array(VER, dtype=object); first = True; tid = 0; day_ = et_u // DAY
for s0 in range(0, NE, 500_000):
    sl = slice(s0, min(NE, s0 + 500_000)); u = eu[sl]; nme = en[sl]; istask = np.isin(nme, [EI['task_created'], EI['task_completed'], EI['task_assigned'], EI['comment_added']]); isproj = istask | (nme == EI['project_created'])
    prop = np.where(nme == EI['integration_connected'], '{"app":"slack"}', np.where(nme == EI['paywall_viewed'], '{"plan":"pro"}', np.where(nme == EI['subscription_started'], '{"source":"checkout"}', None)))
    dd = pd.DataFrame(dict(event_id=eid[sl], event_ts=TS(ev_local[sl]), ingested_at=TS(ingest[sl]), user_id=u, account_id=acct_of_u[u - 1], event_name=EVT[nme], platform=PL[ep[sl]],
        app_version=np.where(r2.random(len(u)) < .02, None, VR[ver[sl]]), session_id='S' + pd.Series(u.astype(np.int64) * 10000 + day_[sl]).astype(str).values,
        project_id=np.where(isproj, acct_of_u[u - 1] * 100 + 1 + u % 6, 0), task_id=np.where(istask, ekey[sl] + 1, 0), properties=prop)); tid += len(u)
    dd['project_id'] = dd.project_id.replace(0, pd.NA).astype('Int64'); dd['task_id'] = dd.task_id.replace(0, pd.NA).astype('Int64')
    dd.to_csv(f'{OUT}/csv/events.csv', mode='w' if first else 'a', header=first, index=False, date_format='%Y-%m-%d %H:%M:%S'); first = False
sizes['events'] = NE
print(json.dumps(sizes, indent=1))
