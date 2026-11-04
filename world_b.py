"""Stages 2,4,5,7 (part 2): users, events, experiments, growth tables, planted problems, _truth, export."""
import os, sys, numpy as np, pandas as pd
from world_a import *
from schema import TABLES

r2 = np.random.default_rng(SEED + 99)
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'data'); os.makedirs(f'{OUT}/csv', exist_ok=True)
EV = ENUMS['event_name']; EI = {n: i for i, n in enumerate(EV)}
aid = A.aid.values

# ---------------------------------------------------------------- per-account facts from subscriptions
start_a = np.full(N, -1); churn_a = np.full(N, 10 ** 10); seats_a = np.zeros(N, int); plan_a = np.array([''] * N, dtype=object)
for j in range(M): start_a[ca[j]] = start[j]; seats_a[ca[j]] = seats0[j]
chd = pd.DataFrame(O['ch'], columns=['sid', 'a', 't', 'invol', 'b1', 'arr', 'rw'])
churn_a[chd.a.values] = chd.t.values
subs['plan_idx'] = subs.account_idx
end_plan = dict(zip(subs.account_idx, subs.plan)); end_status = dict(zip(subs.account_idx, subs.status))
paid_a = start_a >= 0
# B3: unbilled SSO seats on ~8% of active Business accounts
bus_active = np.array([i for i in np.where(paid_a)[0] if end_status[i] == 'active' and end_plan[i] == 'business'])
b3 = r2.choice(bus_active, int(round(.08 * len(bus_active))), replace=False)
sso = np.zeros(N, bool); sso[b3] = True
oth = np.array([i for i in np.where(paid_a)[0] if end_plan.get(i) == 'business' and i not in set(b3)])
sso[oth[r2.random(len(oth)) < .35]] = True
pps_a = {i: 24. for i in b3}; wgt = r2.uniform(.5, 1.5, len(b3)); kx = 220000 / (12 * (wgt * 24).sum())
unb = np.maximum(2, np.rint(wgt * kx)).astype(int); unbilled = np.zeros(N, int); unbilled[b3] = unb

# ---------------------------------------------------------------- users
nfree = 1 + r2.binomial(4, .15 + .35 * e); nfree[kind != 'base'] = 1
npaid = np.clip(np.rint(seats_a * r2.uniform(.6, 1, N)), 2, 120).astype(int)
aha_p = np.clip(.05 + .6 * e ** 1.3 + .06 * treat4, 0, .95)
aha = (r2.random(N) < aha_p) & (cre < TEND - 10 * DAY) & (kind == 'base')
n = np.where(paid_a, npaid, nfree); n = np.where(aha, np.maximum(n, 2), n); n[(cre > TEND - 10 * DAY) & ~paid_a] = 1
n[kind != 'base'] = 1
ai = np.repeat(np.arange(N), n); U = len(ai); st_ = np.cumsum(n) - n; pos = np.arange(U) - st_[ai]
oc = cre[ai]; first = np.where(aha, cre + r2.uniform(.02, 2.9, N) * DAY, cre + 3.5 * DAY + r2.exponential(25 * DAY, N))
gaps = r2.exponential(np.where(paid_a[ai], 4, 18) * DAY, U); gaps[pos <= 1] = 0
created = first[ai] + pd.Series(gaps).groupby(ai).cumsum().values
late = paid_a[ai] & (pos >= 5); created = np.where(late, np.maximum(created, start_a[ai] + r2.uniform(0, 60 * DAY, U)), created)
lim = np.where(churn_a[ai] < 10 ** 9, churn_a[ai] - DAY, TEND - 3600)
created = np.where(pos == 0, oc, np.maximum(np.minimum(created, lim), oc)).astype(np.int64)
# extra SSO-provisioned users (B3): unbilled seats
ex_a = np.repeat(np.arange(N), unbilled); ex_c = np.minimum(start_a[ex_a] + 30 * DAY + r2.uniform(0, 60 * DAY, len(ex_a)), TEND - DAY).astype(np.int64)
ai = np.concatenate([ai, ex_a]); created = np.concatenate([created, ex_c]); pos = np.concatenate([pos, np.full(len(ex_a), 99)])
sso_extra = np.concatenate([np.zeros(U, bool), np.ones(len(ex_a), bool)]); U = len(ai); uid = np.arange(1, U + 1)
owner_uid = np.zeros(N, int); owner_uid[ai[pos == 0]] = uid[pos == 0]
e_u = np.clip(e[ai] + r2.normal(0, .12, U), .01, .99); aha_u = aha[ai]
plat = r2.choice(3, U, p=[.6, .22, .18]); plat[sso_extra] = 0
# user-level experiments 1, 2, 6 (activation) and 4 (owner aha, assigned above at account level)
eff = np.zeros(U); asg = []
for k in (1, 2, 6):
    m = wmask(k, created) & ~sso_extra; tr_ = m & (r2.random(U) < .5); wk = np.clip((created - sec(EXP[k][0])) // (7 * DAY), 0, 5)
    if k == 1: eff += tr_ * np.array([14, 10, 5, 1, 0, 0])[wk]
    if k == 2: eff += tr_ * np.array([8, -7, -7])[plat]
    asg += [(k, uid[i], 'treatment' if tr_[i] else 'control', created[i], plat[i]) for i in np.where(m)[0]]
for i in np.where(m4[ai] & (pos == 0))[0]: asg.append((4, uid[i], 'treatment' if treat4[ai[i]] else 'control', created[i], plat[i]))
will = (r2.random(U) < np.clip(.08 + .7 * e_u ** 1.2 + .2 * aha_u, 0, .97) + eff / 100) & ~sso_extra
pr = np.where(aha_u, .55, .20); ret_p = np.clip(pr + .4 * (e_u - pd.Series(e_u).groupby(aha_u).transform('mean').values), .02, .97)
ret = (r2.random(U) < ret_p) | sso_extra
ret &= ~(churn_a[ai] < created + 98 * DAY)
end = np.where(ret, np.minimum(TEND, created + 98 * DAY + r2.exponential(np.where(paid_a[ai], 800, 250) * DAY, U)), created + np.minimum(84 * DAY - 1, r2.exponential(12 * DAY, U) + DAY))
end = np.minimum(end, np.where(churn_a[ai] < 10 ** 9, churn_a[ai] + 10 * DAY, TEND)).astype(np.int64); end = np.maximum(end, created + 3600)
mature = created + 98 * DAY <= TEND

# ---------------------------------------------------------------- events (kept as numpy arrays; memory-lean)
def mk(u, t, nm): return u, t.astype(np.int64), np.full(len(u), nm, np.int8)
parts = []
ix = np.where(~sso_extra)[0]; parts.append(mk(uid[ix], created[ix], EI['signup_completed']))
parts.append(mk(uid, created + r2.integers(60, 1800, U), EI['session_start']))
ia = np.where(will)[0]; parts.append(mk(uid[ia], created[ia] + r2.uniform(.02, 1.5, len(ia)) * DAY, EI['project_created']))
nt = 3 + r2.poisson(1.5, len(ia)); ru = np.repeat(ia, nt)
parts.append(mk(uid[ru], created[ru] + r2.uniform(.05, 6.9, len(ru)) * DAY, EI['task_completed']))
parts.append(mk(uid[ru], created[ru] + r2.uniform(.02, 6.5, len(ru)) * DAY, EI['task_created']))
inn = np.where(~will & ~sso_extra)[0]; pj = inn[r2.random(len(inn)) < .45]
parts.append(mk(uid[pj], created[pj] + r2.uniform(.02, 3, len(pj)) * DAY, EI['project_created']))
nc = r2.integers(0, 3, len(pj)); rc = np.repeat(pj, nc); parts.append(mk(uid[rc], created[rc] + r2.uniform(.05, 6.9, len(rc)) * DAY, EI['task_completed']))
# invites (P1) and accepts
mem = np.where((pos >= 1) & (pos < 99))[0]; ow = owner_uid[ai[mem]]; ocr = cre[ai[mem]]
inv_t = np.where(aha[ai[mem]] & (pos[mem] == 1), ocr + r2.uniform(.01, 1, len(mem)) * (created[mem] - ocr), np.maximum(created[mem] - r2.uniform(.05, 1.5, len(mem)) * DAY, ocr + 3.01 * DAY))
inv_t = np.minimum(inv_t, created[mem])
parts.append(mk(ow, inv_t, EI['teammate_invited'])); parts.append(mk(uid[mem], created[mem], EI['invite_accepted']))
# conversion funnel events for owners of paid accounts
pa_ = np.where(paid_a)[0]; ou = owner_uid[pa_]; stt = start_a[pa_]
parts.append(mk(ou, stt - r2.uniform(3600, 5 * DAY, len(pa_)), EI['paywall_viewed'])); parts.append(mk(ou, stt - r2.uniform(60, 3600, len(pa_)), EI['upgrade_clicked']))
parts.append(mk(ou, stt - r2.uniform(60, 1200, len(pa_)), EI['checkout_started'])); parts.append(mk(ou, stt, EI['subscription_started']))
# week-12 presence for retained users, then background activity
ri = np.where(ret & mature & ~sso_extra)[0]; parts.append(mk(uid[ri], created[ri] + r2.uniform(84, 98, len(ri)) * DAY, EI['task_completed']))
bs0 = np.where(will | sso_extra, created, created + 7 * DAY); span = np.maximum(end - bs0, 0)
lam = (.4 + 3 * e_u) * (np.maximum(span, 0) / DAY) ** .75 * np.where(sso_extra, .1, 1) * np.where(pos == 0, 1.3, 1)
base_n = sum(len(p[0]) for p in parts); lam *= (3.45e6 - base_n) / lam.sum()
nb = r2.poisson(lam); nb[span <= 0] = 0; ru = np.repeat(np.arange(U), nb)
tb = bs0[ru] + (r2.random(len(ru)) ** 1.6 * span[ru]); BG = np.array([EI[x] for x in ['session_start', 'task_created', 'task_completed', 'comment_added', 'task_assigned', 'project_created', 'integration_connected', 'paywall_viewed']])
nm = BG[r2.choice(8, len(ru), p=[.31, .22, .22, .09, .07, .03, .01, .05])]; parts.append((uid[ru], tb.astype(np.int64), nm.astype(np.int8)))
eu = np.concatenate([p[0] for p in parts]).astype(np.int32); et = np.concatenate([p[1] for p in parts]); en = np.concatenate([p[2] for p in parts]); del parts
o_ = np.argsort(et, kind='stable'); eu, et, en = eu[o_], et[o_], en[o_]; et = np.minimum(et, TEND)
uix = eu - 1; ep = np.where(r2.random(len(eu)) < .9, plat[uix], 0).astype(np.int8)
# P5: Android v4.2.1 double-fires task_completed for 3 weeks
W5 = (sec('2024-10-14'), sec('2024-11-04')); upd = r2.random(U) < .7
ver = np.zeros(len(eu), np.int8)                                   # 0 web,1..: version code
in5 = (ep == 2) & (et >= W5[0]) & (et < W5[1]) & upd[uix]
dup = in5 & (en == EI['task_completed'])
VER = ['web', '3.8.2', '3.9.1', '3.10.0', '3.11.2', '4.0.9', '4.1.4', '4.2.1', '4.2.2']
ver = np.where(ep == 0, 0, np.where(ep == 1, 1 + np.searchsorted([sec('2023-10-01'), sec('2024-06-01'), sec('2025-03-01')], et), np.where(et < sec('2023-12-01'), 5, np.where(et < W5[0], 6, np.where(et < W5[1], np.where(upd[uix], 7, 6), 8))))).astype(np.int8)
di = np.where(dup)[0]; ekey = np.concatenate([np.arange(len(et)), di])
eu = np.concatenate([eu, eu[di]]); et_u = np.concatenate([et, et[di] + r2.integers(0, 2, len(di))]); en = np.concatenate([en, en[di]])
ep = np.concatenate([ep, ep[di]]); ver = np.concatenate([ver, ver[di]]); is_dup = np.concatenate([np.zeros(len(et), bool), np.ones(len(di), bool)])
o_ = np.argsort(et_u, kind='stable'); eu, et_u, en, ep, ver, is_dup, ekey = eu[o_], et_u[o_], en[o_], ep[o_], ver[o_], is_dup[o_], ekey[o_]
NE = len(eu); eid = np.arange(1, NE + 1)
acct_of_u = aid[ai]; tzs_u = (A.tzoff.values[ai] * 3600).astype(int)
dl = r2.random(NE); delay = np.where(dl < .97, r2.exponential(40, NE), np.where(dl < .99, r2.uniform(3600, 3 * DAY, NE), r2.uniform(3 * DAY, 10 * DAY, NE))).astype(np.int64)
ingest = et_u + delay
ev_local = et_u + np.where(ep == 1, tzs_u[eu - 1], 0)               # B5: iOS client sends device-local time
print('events', NE, 'dup rows', is_dup.sum())

# last_active
la = np.zeros(U, np.int64); np.maximum.at(la, eu - 1, et_u)

# ---------------------------------------------------------------- users table
last_a = pd.Series(created).groupby(ai).transform('first').values
dact = np.where(churn_a[ai] < 10 ** 9, True, False); deact_t = np.where(dact, np.minimum(churn_a[ai], TEND), 0)
rd = paid_a[ai] & (pos >= 1) & (r2.random(U) < .06) & ~dact; deact_t = np.where(rd, np.minimum(la + 5 * DAY, TEND), deact_t); dact |= rd
role = np.where(pos == 0, 'owner', np.where(r2.random(U) < .1, 'admin', 'member'))
users = pd.DataFrame(dict(user_id=uid, account_id=aid[ai], email=[f"user{u}@{d or 'mail.example.com'}" for u, d in zip(uid, A.domain.values[ai])], role=role, created_at=ts(created),
    invited_by_user_id=pd.array(np.where((pos >= 1) & (pos < 99), owner_uid[ai], 0), dtype='Int64'), first_platform=np.array(ENUMS['platform'])[plat],
    is_sso_provisioned=sso_extra | (sso[ai] & (pos >= 1)), is_active=~dact, deactivated_at=np.where(dact, ts(deact_t), np.datetime64('NaT')), last_active_at=np.where(la > 0, ts(la), np.datetime64('NaT'))))
users.loc[users.invited_by_user_id == 0, 'invited_by_user_id'] = pd.NA

# ---------------------------------------------------------------- finish billing: post-hoc injections
inv = inv.sort_values(['issued_at', 'ik'], kind='stable').reset_index(drop=True); inv['invoice_id'] = np.arange(1, len(inv) + 1); imap = dict(zip(inv.ik, inv.invoice_id))
pay['invoice_id'] = pay.ik.map(imap); pay = pay.sort_values(['attempted_at', 'pk'], kind='stable').reset_index(drop=True); pay['payment_id'] = np.arange(1, len(pay) + 1)
# B6: pricing bug Mar 3-9 2025 -> 25 Business accounts billed at Pro price on one invoice each
wb = inv[(inv.issued_at >= sec('2025-03-03')) & (inv.issued_at < sec('2025-03-10')) & (inv.plan == 'business') & (inv.status == 'paid')]
b6 = wb.drop_duplicates('account_id').sample(min(25, wb.account_id.nunique()), random_state=SEED).index
lost6 = (inv.loc[b6, 'total_amount'] * inv.loc[b6, 'fx_rate_to_usd']).sum() / 2
for c_ in ('unit_price', 'subtotal', 'discount_amount', 'tax_amount', 'total_amount'): inv.loc[b6, c_] = (inv.loc[b6, c_] / 2).round(2)
inv.loc[b6, 'total_usd'] = (inv.loc[b6, 'total_amount'] * inv.loc[b6, 'fx_rate_to_usd']).round(2)
pm = pay.invoice_id.isin(inv.loc[b6, 'invoice_id']); pay.loc[pm, 'amount'] = pay.loc[pm].invoice_id.map(dict(zip(inv.invoice_id, inv.total_amount)))
# B5: missing fx / unconverted USD / local-time issue stamps
nu = inv.currency != 'USD'; rr = r2.random(len(inv))
b5a = nu & (rr < .12); inv.loc[b5a, ['fx_rate_to_usd', 'total_usd']] = np.nan
b5b = nu & (rr >= .12) & (rr < .15); inv.loc[b5b, 'total_usd'] = inv.loc[b5b, 'total_amount']
tzo = (A.tzoff.values[inv.account_idx.values] * 3600).astype(int); loc = inv.currency.isin(['INR', 'EUR']).values
inv['issued_at_utc'] = inv.issued_at; inv.loc[loc, 'issued_at'] += tzo[loc]
# B7: duplicate refunds
sp = pay[(pay.status == 'succeeded')].sample(frac=.022, random_state=SEED + 1).sort_values('payment_id')
nr = len(sp); amt = np.where(r2.random(nr) < .7, sp.amount.values, (sp.amount.values * r2.uniform(.3, .8, nr)).round(2))
refunds = pd.DataFrame(dict(payment_id=sp.payment_id.values, invoice_id=sp.invoice_id.values, account_id=sp.account_id.values,
    refunded_at=np.minimum(sp.attempted_at.values + r2.uniform(3600, 20 * DAY, nr), TEND).astype(np.int64), amount=amt, currency=sp.currency.values,
    reason=r2.choice(ENUMS['refund_reason'], nr, p=[.45, .1, .25, .15, .05]), status='succeeded', issued_by=np.where(r2.random(nr) < .25, 'system', [f"agent_{i}" for i in r2.integers(1, 13, nr)])))
refunds['dup'] = False; nd7 = max(5, int(round(.004 * nr))); dsel = refunds.sample(nd7, random_state=SEED + 2).copy()
dsel['refunded_at'] += r2.integers(5, 180, nd7); dsel['dup'] = True; refunds = pd.concat([refunds, dsel]).sort_values('refunded_at', kind='stable').reset_index(drop=True)
refunds['refund_id'] = np.arange(1, len(refunds) + 1); refunds['processor_refund_id'] = [f"re_{i:07d}" for i in refunds.refund_id]
refunds.loc[refunds.dup & (r2.random(len(refunds)) < .0), 'issued_by'] = 'system'

# redemptions & coupons
red = pd.DataFrame(RR, columns=['coupon_id', 'account_idx', 'subscription_id', 'redeemed_at', 'ends', 'redemption_channel']).sort_values('redeemed_at', kind='stable').reset_index(drop=True)
red['redemption_id'] = np.arange(1, len(red) + 1); red['account_id'] = aid[red.account_idx.values]
# remap invoice coupon_redemption_id (stored as coupon id) -> redemption id
rkey = {(s, c): i for s, c, i in zip(red.subscription_id, red.coupon_id, red.redemption_id)}
inv['coupon_redemption_id'] = [rkey.get((s, int(c))) if pd.notna(c) else None for s, c in zip(inv.subscription_id, inv.coupon_redemption_id)]
# subscriptions: self-reported cancel reason + truth reasons
subs = subs.sort_values('subscription_id').reset_index(drop=True)
chd['rw'] = chd.rw.astype(bool); tc = chd.copy(); low = e[tc.a.values] < .4
def pick(i):
    if tc.invol[i]: return 'payment_failure'
    return r2.choice(['price', 'missing_feature', 'low_adoption', 'competitor', 'team_shrunk', 'project_ended'], p=[.18, .13, .34, .13, .11, .11] if low[i] else [.22, .18, .12, .16, .16, .16])
tc['true_reason'] = [pick(i) for i in range(len(tc))]
vague = {'price': ['too_expensive', 'too_expensive', 'other'], 'missing_feature': ['missing_features', 'switched_tool', 'other'], 'low_adoption': ['not_using', 'other', 'too_expensive'],
         'competitor': ['switched_tool', 'too_expensive'], 'team_shrunk': ['team_changed', 'other'], 'project_ended': ['project_ended', 'other']}
sr = {s: (None if (r2.random() < .45 or t == 'payment_failure') else r2.choice(vague[t])) for s, t in zip(tc.sid, tc.true_reason)}
subs['cancel_reason_self_reported'] = subs.subscription_id.map(sr)

# ---------------------------------------------------------------- marketing / platform data (G1, G2)
CPS = dict(paid_search=55., paid_social=38., review_site=14., affiliate=25.); MULT = dict(paid_search=1.3, paid_social=1.6, review_site=1.0, affiliate=1.1)
AM = dict(paid_search='click_7d_view_1d', paid_social='click_7d_view_1d', review_site='click_28d', affiliate='click_30d_view_7d')
fp = pay[pay.status == 'succeeded'].groupby('account_idx').attempted_at.min()
A['first_paid'] = A.index.map(fp)
d_all = pd.date_range(START_DATE, END_DATE); rows_m = []; rows_p = []; sid_ = 0
sig = pd.DataFrame(dict(d=(cre // DAY), ch=np.array(CH)[ch], camp=A.campaign.values))
arr0 = pd.Series(0., index=range(N))
for j in range(M): arr0[ca[j]] = 12 * (seats0[j] * PR[plan0[j]] * (.8 if itv0[j] == 'annual' else 1))
cvd = pd.DataFrame(dict(d=(A.first_paid.values // DAY), ch=np.array(CH)[ch], camp=A.campaign.values, arr=arr0.values)).dropna(subset=['d'])
cvd = cvd[cvd.arr > 0]
sg = sig.groupby(['ch', 'camp', 'd']).size(); cg = cvd.groupby(['ch', 'camp', 'd']).agg(n=('arr', 'size'), arr=('arr', 'sum'))
for c_ in CPS:
    for cm in CAMP[c_]:
        s_ = sg.get((c_, cm), pd.Series(dtype=int)) if False else sg.xs((c_, cm)) if (c_, cm) in sg.index.droplevel(2) else pd.Series(dtype=int)
        n_s = s_.reindex(range(len(d_all)), fill_value=0).values; cc_ = cg.xs((c_, cm)) if (c_, cm) in cg.index.droplevel(2) else pd.DataFrame(columns=['n', 'arr'])
        n_c = cc_.n.reindex(range(len(d_all)), fill_value=0).values; a_c = cc_.arr.reindex(range(len(d_all)), fill_value=0.).values
        sp_ = np.maximum(5, (n_s + .3) * CPS[c_] * r2.lognormal(0, .25, len(d_all))).round(2)
        cur_ = np.where(r2.random(len(d_all)) < .2, np.where(r2.random(len(d_all)) < .5, 'EUR', 'GBP'), 'USD')
        loc_ = np.array([FXB[c] for c in cur_]); sp_l = (sp_ / loc_).round(2); usd = np.where((cur_ != 'USD') & (r2.random(len(d_all)) < .35), np.nan, sp_)
        rows_m.append(pd.DataFrame(dict(spend_date=d_all, channel=c_, campaign=cm, impressions=(sp_ * r2.uniform(120, 220, len(d_all))).astype(int), clicks=(n_s * r2.uniform(15, 35, len(d_all)) + sp_ / 2).astype(int), spend_amount=sp_l, currency=cur_, spend_usd=usd)))
        rows_p.append(pd.DataFrame(dict(report_date=d_all, channel=c_, campaign=cm, attribution_model=AM[c_], platform_signups=np.rint(n_s * MULT[c_] * r2.lognormal(0, .12, len(d_all))).astype(int),
            platform_paid_conversions=np.rint(n_c * MULT[c_] * r2.lognormal(0, .1, len(d_all))).astype(int), platform_revenue_usd=(a_c * MULT[c_]).round(2))))
mkt = pd.concat(rows_m, ignore_index=True); mkt['spend_id'] = np.arange(1, len(mkt) + 1)
plat_rep = pd.concat(rows_p, ignore_index=True); plat_rep['report_id'] = np.arange(1, len(plat_rep) + 1)

# ---------------------------------------------------------------- leads & sales touches
LS = lambda c: rng_lab(c)
def rng_lab(c): return r2.choice(MESSY[c]) if r2.random() < .15 else c
sa = np.where(sales)[0]; lc = np.maximum(0, cre[sa] - r2.uniform(1, 30, len(sa)) * DAY).astype(np.int64); wonm = paid_a[sa]
st_s = np.where(wonm, r2.choice(['won'], len(sa)), r2.choice(['lost', 'opportunity', 'sql', 'mql'], len(sa), p=[.5, .15, .15, .2]))
fa = np.where(wonm, start_a[sa], 0)
L1 = pd.DataFrame(dict(created_at=lc, acct=sa, company_name=A.name.values[sa], email_domain=A.domain.values[sa], company_size_band=np.array(ENUMS['company_size_band'])[A['size'].values[sa]],
    lead_source=[('outbound' if r2.random() < .4 else rng_lab(CH[ch[i]])) for i in sa], lead_status=st_s, closed_at=np.where(wonm, fa, np.where(st_s == 'lost', lc + r2.uniform(15, 90, len(sa)) * DAY, 0)).astype(np.int64),
    deal_arr_usd=np.where(wonm, arr0.values[sa].round(2), np.nan)))
nl = 5600; lc2 = (rng.choice(len(dates), nl, p=w / w.sum()) * DAY + r2.integers(0, DAY, nl)).astype(np.int64); s2 = r2.choice(['new', 'mql', 'sql', 'opportunity', 'lost'], nl, p=[.3, .25, .15, .08, .22])
L2 = pd.DataFrame(dict(created_at=lc2, acct=-1, company_name=[f"Prospect {W50[i % 50]} {C20[(i // 50) % 20]}" for i in range(nl)], email_domain=[f"prospect{i}.com" for i in range(nl)],
    company_size_band=r2.choice(ENUMS['company_size_band'], nl, p=[.1, .3, .3, .2, .1]), lead_source=[rng_lab(c) if r2.random() > .35 else 'outbound' for c in r2.choice(CH, nl)], lead_status=s2,
    closed_at=np.where(s2 == 'lost', lc2 + r2.uniform(10, 90, nl) * DAY, 0).astype(np.int64), deal_arr_usd=np.nan))
leads = pd.concat([L1, L2]).sort_values('created_at', kind='stable').reset_index(drop=True); leads['lead_id'] = np.arange(1, len(leads) + 1)
rank = {'new': 0, 'mql': 1, 'sql': 2, 'opportunity': 3, 'won': 4, 'lost': 2}; lv = leads.lead_status.map(rank).values
for nm_, k_ in (('mql_at', 1), ('sql_at', 2), ('opportunity_at', 3)):
    leads[nm_] = np.where(lv >= k_, leads.created_at + (k_ * r2.uniform(1, 12, len(leads)) * DAY), 0).astype(np.int64)
leads['owner_rep_id'] = r2.integers(1, 9, len(leads)); leads['loss_reason'] = np.where(leads.lead_status == 'lost', r2.choice(['price', 'no_budget', 'competitor', 'no_response', 'bad_fit'], len(leads)), None)
amap = dict(zip(leads.acct[leads.acct >= 0], leads.lead_id[leads.acct >= 0])); A['lead_id'] = [amap.get(i) for i in range(N)]
nt_ = 1 + r2.poisson(np.where(leads.lead_status == 'won', 6, 3), len(leads)); rl = np.repeat(np.arange(len(leads)), nt_)
endl = np.where(leads.closed_at.values > 0, leads.closed_at.values, TEND)[rl]; tt = leads.created_at.values[rl] + r2.random(len(rl)) * np.maximum(endl - leads.created_at.values[rl], 3600)
touches = pd.DataFrame(dict(lead_id=leads.lead_id.values[rl], account_idx=leads.acct.values[rl], rep_id=leads.owner_rep_id.values[rl], touched_at=tt.astype(np.int64),
    touch_type=r2.choice(ENUMS['touch_type'], len(rl), p=[.4, .25, .2, .08, .07]), outcome=r2.choice(ENUMS['touch_outcome'], len(rl), p=[.3, .3, .15, .15, .1]), duration_minutes=0))
touches['duration_minutes'] = np.where(touches.touch_type.isin(['call', 'demo']), r2.integers(10, 75, len(touches)), None)
touches = touches.sort_values('touched_at', kind='stable').reset_index(drop=True); touches['touch_id'] = np.arange(1, len(touches) + 1)
touches['account_id'] = [aid[i] if i >= 0 else None for i in touches.account_idx]
