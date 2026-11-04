"""Stages 2-3 (part 1): accounts, coupons, subscriptions, plan_changes, invoices, payments, refunds.
Planted here: B1 (dunning outage), B2 (coupon stacking), B4 (dups), B5 (fx/tz), B6 (price bug), B7 (dup refunds), G4 (labels)."""
import numpy as np, pandas as pd, datetime as dtm
from config import *

DAY = 86400
PY0 = dtm.datetime(2023, 1, 1); T0 = np.datetime64('2023-01-01T00:00:00')
TEND = int((dtm.datetime(2025, 12, 31, 23, 59, 59) - PY0).total_seconds())
sec = lambda s: int((pd.Timestamp(s).to_pydatetime() - PY0).total_seconds())
ts = lambda a: T0 + np.asarray(a).astype('int64').astype('timedelta64[s]')

def addm(s, n):
    d = PY0 + dtm.timedelta(seconds=int(s)); y, m = divmod(d.month - 1 + n, 12)
    return int((d.replace(year=d.year + y, month=m + 1, day=min(d.day, 28)) - PY0).total_seconds())

def msec(s, n):
    d = PY0 + dtm.timedelta(seconds=int(s)); y, m = divmod(d.month - 1 + n, 12)
    return int((dtm.datetime(d.year + y, m + 1, 1) - PY0).total_seconds())

rng = np.random.default_rng(SEED)
EXP = {1: ('2023-09-04', '2023-10-15'), 2: ('2024-02-05', '2024-03-18'), 3: ('2024-05-06', '2024-06-17'),
       4: ('2024-08-05', '2024-09-16'), 5: ('2025-01-13', '2025-02-24'), 6: ('2025-04-07', '2025-05-19')}
wmask = lambda k, c: (c >= sec(EXP[k][0])) & (c < sec(EXP[k][1]) + DAY)

# ------------------------------------------------------------------ accounts
NB, ND, NT = 38960, 974, 40; N = NB + ND + NT
CH = ['organic_search', 'direct', 'referral', 'paid_search', 'paid_social', 'review_site', 'affiliate', 'content_email', 'partner']
CHP = [.22, .14, .08, .16, .12, .08, .04, .10, .06]
CESH = np.array([0, 0, .08, 0, -.03, -.14, 0, .02, .1])
CW = np.array([1, 1.1, 1.3, .9, .7, .12, .8, .9, 1.4])
CTRY = ['US', 'GB', 'DE', 'FR', 'CA', 'IN', 'AU', 'NL', 'BR', 'ES']; CP = [.48, .08, .07, .04, .06, .09, .04, .03, .04, .07]
CUR = dict(US='USD', GB='GBP', DE='EUR', FR='EUR', CA='CAD', IN='INR', AU='USD', NL='EUR', BR='USD', ES='EUR')
TAX = dict(US=0, GB=.2, DE=.19, FR=.2, CA=.05, IN=.18, AU=0, NL=.21, BR=0, ES=.21)
TZ = dict(US=[('America/New_York', -5), ('America/Chicago', -6), ('America/Los_Angeles', -8)], GB=[('Europe/London', 0)],
          DE=[('Europe/Berlin', 1)], FR=[('Europe/Paris', 1)], CA=[('America/Toronto', -5)], IN=[('Asia/Kolkata', 5.5)],
          AU=[('Australia/Sydney', 10)], NL=[('Europe/Amsterdam', 1)], BR=[('America/Sao_Paulo', -3)], ES=[('Europe/Madrid', 1)])
MESSY = {'organic_search': ['Organic', 'organic search', 'google organic', 'SEO', 'Organic Search '], 'direct': ['(direct)', 'Direct', 'none', 'direct / none'],
         'referral': ['Referral', 'word of mouth', 'referral_friend', 'ref'], 'paid_search': ['Google Ads', 'google / cpc', 'adwords', 'GoogleAds', 'PPC'],
         'paid_social': ['FB', 'facebook ads', 'Facebook', 'LinkedIn Ads', 'social_paid'], 'review_site': ['G2', 'g2 crowd', 'Capterra', 'capterra review', 'GetApp'],
         'affiliate': ['partnerstack', 'Affiliate', 'aff'], 'content_email': ['newsletter', 'Email', 'blog'], 'partner': ['Partner', 'partners', 'integration_partner']}
CAMP = {'paid_search': ['search_brand', 'search_generic', 'search_competitor'], 'paid_social': ['social_prospecting', 'social_retargeting', 'social_lookalike'],
        'review_site': ['reviews_g2', 'reviews_capterra', 'reviews_getapp'], 'affiliate': ['aff_network_a', 'aff_network_b', 'aff_creators']}
W50 = ("Nor Blue Red Sun Moon Star Iron Gold Silver Oak Pine River Lake Stone Cloud Bright Swift Bold True Prime Apex Nova Zen Echo Orbit Pulse Spark "
       "Quartz Maple Cedar Harbor Summit Atlas Vista Pixel Cobalt Amber Ivory Coral Delta North Ridge Bay Fern Glen Hawk Lark Mesa Opal Reef").split()
C20 = "Labs Studio Group Co Systems Partners Works Digital Health Capital Media Logistics Consulting Design Software Analytics Foods Energy Learning Ventures".split()

dates = pd.date_range(START_DATE, END_DATE); mi = (dates.year - 2023) * 12 + dates.month - 1
tr = np.where(mi >= 24, 2.6 * .97, 1 + 1.6 * np.minimum(mi, 23) / 23)
w = tr * np.array([1.15, 1.05, 1.05, 1, .95, .9, .85, .85, 1.1, 1.1, 1, .8])[dates.month - 1] * np.array([1, 1, 1, 1, .9, .45, .4])[dates.dayofweek]
dy = rng.choice(len(dates), NB, p=w / w.sum())
cre0 = dy * DAY + (rng.normal(14, 3.5, NB) % 24 * 3600).astype(int) + rng.integers(0, 3600, NB)
perm = rng.permutation(50 * 50 * 20)[:NB]; a_, b_, c_ = perm % 50, (perm // 50) % 50, perm // 2500
ch0 = rng.choice(9, NB, p=CHP); ctry0 = rng.choice(CTRY, NB, p=CP)
tzi = [rng.integers(len(TZ[c])) for c in ctry0]
B = pd.DataFrame(dict(key=np.arange(NB), kind='base', orig=-1, cre=cre0,
    name=[f"{W50[a]} {W50[b]} {C20[c]}" for a, b, c in zip(a_, b_, c_)],
    domain=[f"{W50[a]}{W50[b]}{C20[c]}".lower() + ".com" for a, b, c in zip(a_, b_, c_)],
    ch=ch0, country=ctry0, tz=[TZ[c][i][0] for c, i in zip(ctry0, tzi)], tzoff=[TZ[c][i][1] for c, i in zip(ctry0, tzi)],
    size=rng.choice(5, NB, p=[.45, .3, .15, .07, .03]),
    industry=np.where(rng.random(NB) < .35, None, rng.choice(E['industry'] if False else ENUMS['industry'], NB)),
    e=np.clip(rng.beta(2.2, 2.6, NB) + CESH[ch0], .02, .98)))
B.loc[rng.random(NB) < .18, 'domain'] = None                      # personal webmail owners
# B4: duplicate accounts (same owner re-signs up within 30 days under a name variant)
o = rng.choice(NB, ND, replace=False); Dp = B.iloc[o].copy(); Dp['kind'] = 'dup'; Dp['orig'] = o; Dp['key'] = NB + np.arange(ND)
Dp['cre'] = np.minimum(Dp.cre.values + rng.integers(DAY // 2, 30 * DAY, ND), TEND - 1)
var = [lambda s: s.lower(), lambda s: s.rsplit(' ', 1)[0], lambda s: s + ' Inc', lambda s: s.upper(), lambda s: s.replace(' ', '')]
Dp['name'] = [var[i](n) for i, n in zip(rng.integers(0, 5, ND), Dp.name)]
Tt = B.iloc[rng.choice(NB, NT, replace=False)].copy(); Tt['kind'] = 'test'; Tt['key'] = NB + ND + np.arange(NT); Tt['orig'] = -1
Tt['name'] = [f"Flowdesk Test {i}" for i in range(NT)]; Tt['domain'] = 'flowdesk.com'; Tt['cre'] = rng.integers(0, TEND - DAY, NT)
A = pd.concat([B, Dp, Tt]).sort_values('cre', kind='stable').reset_index(drop=True)
A['aid'] = np.arange(1, N + 1); k2i = dict(zip(A.key, A.index)); A['oi'] = A.orig.map(lambda k: k2i.get(k, -1))
assert len(A) == N
cre = A.cre.values; kind = A.kind.values; ch = A.ch.values; e = A.e.values; base_m = kind == 'base'
A['currency'] = A.country.map(CUR); A['tax'] = A.country.map(TAX)
# G4 messy labels (15%) + UTM
messy = rng.random(N) < .15
lab = np.array(CH)[ch].astype(object)
for i in np.where(messy)[0]: lab[i] = rng.choice(MESSY[CH[ch[i]]])
A['signup_source'] = lab; A['messy'] = messy
cp = np.array([rng.choice(CAMP[CH[c]]) if CH[c] in CAMP else None for c in ch], dtype=object)
paid = np.isin(ch, [3, 4, 5, 6]); has_utm = paid & (rng.random(N) > .25)
A['campaign'] = cp
A['utm_campaign'] = np.where(has_utm, cp, None)
A['utm_source'] = np.where(has_utm, np.array(['google', 'facebook', 'g2', 'partnerstack'], dtype=object)[np.clip(ch - 3, 0, 3)], np.where(ch == 7, 'newsletter', None))
A['utm_medium'] = np.where(has_utm, np.array(['cpc', 'paid_social', 'review', 'affiliate'], dtype=object)[np.clip(ch - 3, 0, 3)], np.where(ch == 7, 'email', None))
A.loc[rng.random(N) < .02, 'country'] = None                       # noise: missing country
# ------------------------------------------------------------------ experiments on account unit (3: pricing page w/ SRM, 5: annual banner)
ctrl3 = rng.random(N) < .523                                       # P2: 52.3/47.7 instead of 50/50
m3 = wmask(3, cre); treat3 = m3 & ~ctrl3
m5 = wmask(5, cre); treat5 = m5 & (rng.random(N) < .5)
m4 = wmask(4, cre) & (kind == 'base'); treat4 = m4 & (rng.random(N) < .5)   # exp4 randomizes owners (unit=user)
# ------------------------------------------------------------------ sales-assisted + conversion
NS = 920
sw = np.where(base_m, np.array([.2, .6, 1.8, 3.5, 5])[A['size'].values], 0.)
sales = np.zeros(N, bool); sales[rng.choice(N, NS, replace=False, p=sw / sw.sum())] = True
A['motion'] = np.where(sales, 'sales_assisted', 'self_serve')
y25 = cre >= sec('2025-01-01')
wc = CW[ch] * (.15 + e ** 1.5 * 1.8) * np.where(y25, .6, 1.) * (base_m & ~sales)
kk = 3650 / wc.sum(); pconv = np.clip(kk * wc + .03 * treat3 * (wc > 0), 0, .9); pconv = np.where(sales, .65, pconv)
conv = rng.random(N) < pconv
lag = np.where(sales, rng.lognormal(np.log(35 * DAY), .6, N), rng.lognormal(np.log(18 * DAY), .9, N)).astype(int) + 3600
start_all = cre + lag; conv &= start_all < TEND - DAY
cv = np.where(conv)[0]; cv = cv[np.argsort(start_all[cv], kind='stable')]; M = len(cv)
ca = cv; start = start_all[cv]; sales_j = sales[cv]; e_j = e[cv]
size_j = A['size'].values[cv]; ch_j = ch[cv]
pb = np.where(sales_j, .55, .17 + .12 * (size_j >= 2)); plan0 = np.where(rng.random(M) < pb, 'business', 'pro')
pa = np.where(sales_j, .70, .28 + .12 * treat5[cv]); itv0 = np.where(rng.random(M) < pa, 'annual', 'monthly')
bs = np.maximum(1, rng.lognormal(np.log(4.2), .65, M)) * np.where(sales_j, 2.1, 1) * np.where(plan0 == 'business', 1.35, 1)
pm0 = np.where((sales_j & (itv0 == 'annual')) & (rng.random(M) < .5), 'wire', np.where(rng.random(M) < .12, 'ach', 'card'))
fchurn = np.exp(-2.2 * (e_j - .5)) * np.where(sales_j, .6, 1) * np.where(ch_j == 5, 2.2, 1)
cur_j = A.currency.values[cv]; tax_j = A.tax.values[cv]

# ------------------------------------------------------------------ coupons
CPN = [('FALL24', 'FALL24-PROMO', 'percent', 20, None, 'repeating', 12, False, '2024-09-01', '2025-01-31'),
       ('PARTNER24', 'PARTNER-2024', 'percent', 15, None, 'repeating', 12, False, '2024-09-01', '2025-01-31'),
       ('WINBACK24', 'WINBACK-2024', 'percent', 25, None, 'repeating', 12, False, '2024-09-01', '2025-01-31'),
       ('BF24', 'BLACKFRIDAY24', 'percent', 30, None, 'repeating', 12, False, '2024-11-15', '2025-01-31'),
       ('LOYALTY5', 'LOYALTY', 'percent', 5, None, 'forever', None, True, '2023-01-01', '2025-12-31'),
       ('FIXED25', 'SUPPORT', 'fixed', None, 25, 'once', None, False, '2023-01-01', '2025-12-31'),
       ('WELCOME10', 'WELCOME', 'percent', 10, None, 'once', None, False, '2023-01-01', '2025-12-31')]
for yy in (23, 24, 25):
    Y = 2000 + yy
    CPN += [(f'SPRING{yy}', 'SPRING-SALE', 'percent', 15, None, 'repeating', 3, False, f'{Y}-03-01', f'{Y}-04-30'),
            (f'SUMMER{yy}', 'SUMMER-SALE', 'percent', 10, None, 'repeating', 2, False, f'{Y}-06-01', f'{Y}-08-31'),
            (f'EDU{yy}', 'EDU', 'percent', 20, None, 'repeating', 12, False, f'{Y}-01-01', f'{Y}-12-31'),
            (f'STARTUP{yy}', 'STARTUP', 'percent', 20, None, 'repeating', 6, False, f'{Y}-01-01', f'{Y}-12-31'),
            (f'NONPROFIT{yy}', 'NONPROFIT', 'percent', 25, None, 'forever', None, False, f'{Y}-01-01', f'{Y}-12-31'),
            (f'REFER{yy}', 'REFERRAL', 'percent', 10, None, 'once', None, False, f'{Y}-01-01', f'{Y}-12-31')]
coupons = pd.DataFrame(CPN, columns=['code', 'campaign', 'discount_type', 'percent_off', 'amount_off_usd', 'duration', 'duration_months', 'stackable', 'valid_from', 'valid_to'])
coupons.insert(0, 'coupon_id', np.arange(1, len(coupons) + 1)); coupons['max_redemptions'] = None
for c_ in ('valid_from', 'valid_to'): coupons[c_] = pd.to_datetime(coupons[c_])
assert len(coupons) == 25
cvf = coupons.valid_from.map(lambda d: sec(d)).values; cvt = coupons.valid_to.map(lambda d: sec(d) + DAY).values
reds = [[] for _ in range(M)]; RR = []; stackset = set()
w_idx = np.where((start >= sec('2024-09-01')) & (start < sec('2025-02-01')))[0]
for j in rng.choice(w_idx, min(140, len(w_idx)), replace=False):
    ok = [i for i in range(4) if cvf[i] <= start[j] < cvt[i]]; kq = min(len(ok), 3 if rng.random() < .75 else 2)
    for i in rng.choice(ok, kq, replace=False): reds[j].append([int(i) + 1, True]); stackset.add(j)
for j in range(M):
    if j in stackset or rng.random() > .2: continue
    ok = [i for i in range(4, 25) if cvf[i] <= start[j] < cvt[i]]
    if ok: reds[j].append([int(rng.choice(ok)) + 1, False])
for j in range(M):
    for rd in reds[j]:
        c_ = coupons.iloc[rd[0] - 1]; s0 = start[j]
        end = {'once': s0 + 1, 'forever': 10 ** 10}.get(c_.duration) or addm(s0, int(c_.duration_months))
        rd += [(c_.percent_off or 0) / 100, c_.amount_off_usd or 0., end]
        RR.append((rd[0], int(ca[j]), j + 1, s0 + int(rng.integers(0, 7200)), None if end > 10 ** 9 else end,
                   'sales_rep' if sales_j[j] and rng.random() < .6 else ('support' if rng.random() < .08 else 'checkout')))

# ------------------------------------------------------------------ billing simulation
PR = {'pro': 12., 'business': 24.}; FXB = dict(USD=1, EUR=1.08, GBP=1.26, CAD=.74, INR=.012)
fx = lambda c, s: round(FXB[c] * (1 + .03 * np.sin(s / DAY / 120)), 5)
YF = lambda s: 1.15 if s < sec('2024-01-01') else (1.0 if s < sec('2025-01-01') else 2.2)
B1W = (sec('2025-02-01'), sec('2025-07-01'))
FC = ['card_declined', 'insufficient_funds', 'expired_card', 'processor_error']

def sim(S, seed=SEED + 7):
    r = np.random.default_rng(seed); seats0 = np.maximum(2, np.rint(bs * S)).astype(int)
    O = dict(sub=[], pc=[], inv=[], pay=[], seat=[], ch=[]); ik = pk = 0
    for j in range(M):
        a = int(ca[j]); cur = int(start[j]); plan = plan0[j]; itv = itv0[j]; seats = int(seats0[j]); sid = j + 1; first = True
        cc = cur_j[j]; trate = tax_j[j]; mth = pm0[j]; salesj = 'sales' if sales_j[j] else 'customer'
        mrr = lambda: seats * PR[plan] * (.8 if itv == 'annual' else 1)
        O['pc'].append((sid, a, cur, 'start_paid', None, plan, None, itv, None, seats, 0., mrr(), salesj))
        status = 'active'; canc = csrc = None; b1 = False; rw = False; lps, lpe = cur, cur; arr_at = 0
        while True:
            ann = itv == 'annual'; mon = 12 if ann else 1; pps = PR[plan] * (.8 if ann else 1); nxt = addm(cur, 12 if ann else 1)
            f = fx(cc, cur); sub_usd = seats * pps * mon
            act = [c for c in reds[j] if cur < c[4]]
            pct = min(.95, sum(c[2] for c in act)) if act else 0.; dsc = min(sub_usd, sub_usd * pct + sum(c[3] for c in act))
            unit = round(pps / f, 2); sub_l = round(seats * pps * mon / f, 2); dsc_l = round(dsc / f, 2); tax_l = round((sub_l - dsc_l) * trate, 2)
            tot = round(sub_l - dsc_l + tax_l, 2)
            void = r.random() < .003; ist = 'void' if void else 'paid'; ikey = ik; ik += 1; fin = None
            if not void:
                fail = mth != 'wire' and r.random() < TARGETS['payment_failure_rate'] * (1.2 if B1W[0] <= cur < B1W[1] else 1)
                p1 = (pk, ikey, a, 1, cur + int(r.integers(0, 120)), tot, cc, 'succeeded', None, mth); pk += 1
                if fail:
                    outs = [r.random() < q for q in (.35, .30, .25)]; code = r.choice(FC, p=[.45, .3, .2, .05])
                    O['pay'].append(p1[:7] + ('failed', code, mth, f"ch_{pk:08d}"))
                    inwin = B1W[0] <= cur < B1W[1]; rec = False
                    if inwin:                                    # B1: dunning retries silently not running
                        b1 = True; rw = any(outs); ist = 'uncollectible'; fin = cur + 10 * DAY
                    else:
                        for n_, (d_, ok_) in enumerate(zip((1, 3, 7), outs)):
                            pk += 1; t_ = cur + d_ * DAY + int(r.integers(0, 600))
                            O['pay'].append((pk, ikey, a, n_ + 2, t_, tot, cc, 'succeeded' if ok_ else 'failed', None if ok_ else r.choice(FC), mth, f"ch_{pk:08d}"))
                            if ok_: rec = True; break
                        if not rec: ist = 'uncollectible'; fin = cur + 8 * DAY
                else: O['pay'].append(p1 + (f"ch_{pk:08d}",))
            O['inv'].append((ikey, sid, a, cur, cur + 14 * DAY, cur, nxt, 'subscription_create' if first else 'subscription_cycle', seats, cc, unit, sub_l, dsc_l, tax_l, tot, f,
                             round(tot * f, 2), act[0][0] if act else None, ist, plan, any(c[1] for c in act), bool(b1 and fin)))
            first = False
            if fin is not None:
                if fin > TEND: status = 'past_due'; lps, lpe = cur, nxt
                else: status = 'canceled'; canc = fin; csrc = 'payment_failure'; arr_at = mrr() * 12; O['ch'].append((sid, a, fin, True, b1, arr_at, rw)); O['pc'].append((sid, a, fin, 'cancel', plan, None, itv, None, seats, None, mrr(), 0., 'system'))
                break
            if not void:
                for m_ in range(mon):
                    ms = msec(cur, m_)
                    if ms <= TEND: O['seat'].append((a, ms, plan, seats))
            lps, lpe = cur, nxt
            if nxt > TEND: break
            h = .12 if ann else .02; h = min(.6, h * fchurn[j] * YF(nxt) * (.8 if plan == 'business' else 1))
            if r.random() < h:
                canc = max(cur + DAY, nxt - int(r.integers(1, 25)) * DAY); csrc = 'user' if r.random() > .03 else 'admin'; status = 'canceled'
                arr_at = mrr() * 12; O['ch'].append((sid, a, nxt, False, False, arr_at, False)); O['pc'].append((sid, a, canc, 'cancel', plan, None, itv, None, seats, None, mrr(), 0., 'customer')); break
            # renewal-time changes
            yf = .5 if nxt >= sec('2025-01-01') else 1.
            u = r.random(4); sm = 3 if ann else 1
            if u[0] < .07 * sm * yf:
                d = max(1, int(round(seats * r.uniform(.05, .25)))) if r.random() < .8 else -max(1, int(round(seats * .1)))
                ns = max(1, seats + d); m0 = mrr(); O['pc'].append((sid, a, nxt, 'seat_change', plan, plan, itv, itv, seats, ns, m0, ns * PR[plan] * (.8 if ann else 1), 'customer')); seats = ns
            if plan == 'pro' and u[1] < .008 * sm * yf:
                m0 = mrr(); O['pc'].append((sid, a, nxt, 'upgrade', 'pro', 'business', itv, itv, seats, seats, m0, seats * 24 * (.8 if ann else 1), 'sales' if sales_j[j] else 'customer')); plan = 'business'
            elif plan == 'business' and u[2] < .003 * sm:
                m0 = mrr(); O['pc'].append((sid, a, nxt, 'downgrade', 'business', 'pro', itv, itv, seats, seats, m0, seats * 12 * (.8 if ann else 1), 'customer')); plan = 'pro'
            if not ann and u[3] < .004:
                m0 = mrr(); O['pc'].append((sid, a, nxt, 'interval_switch', plan, plan, 'monthly', 'annual', seats, seats, m0, seats * PR[plan] * .8, 'customer')); itv = 'annual'
            cur = nxt
        mrr_end = 0. if status == 'canceled' else mrr()
        O['sub'].append((sid, a, plan, itv, seats, round(PR[plan] * (.8 if itv == 'annual' else 1), 2), round(mrr_end, 2), status, int(start[j]), lps, lpe, canc, csrc))
    return O, seats0

def arr_of(O): return 12 * sum(s[6] for s in O['sub'])
O, seats0 = sim(1.0); S = TARGETS['end_arr_usd'] / arr_of(O)
O, seats0 = sim(S); S2 = TARGETS['end_arr_usd'] / arr_of(O)
if abs(S2 - 1) > .03: O, seats0 = sim(S * S2); S *= S2
SEAT_SCALE = S

# ------------------------------------------------------------------ assemble billing frames
def df(rows, cols): return pd.DataFrame(rows, columns=cols)
subs = df(O['sub'], ['subscription_id', 'account_id', 'plan', 'billing_interval', 'seats', 'price_per_seat_usd', 'mrr_usd', 'status', 'started_at', 'current_period_start', 'current_period_end', 'canceled_at', 'cancellation_source'])
subs['account_idx'] = subs.account_id.astype(int)             # holds account *index*; remapped below
subs['account_id'] = A.aid.values[subs.account_idx.values]
inv = df(O['inv'], ['ik', 'subscription_id', 'account_idx', 'issued_at', 'due_at', 'period_start', 'period_end', 'billing_reason', 'seats_billed', 'currency', 'unit_price', 'subtotal',
                    'discount_amount', 'tax_amount', 'total_amount', 'fx_rate_to_usd', 'total_usd', 'coupon_redemption_id', 'status', 'plan', 'stacked', 'b1'])
inv['account_id'] = A.aid.values[inv.account_idx.values]
pay = df(O['pay'], ['pk', 'ik', 'account_idx', 'attempt_number', 'attempted_at', 'amount', 'currency', 'status', 'failure_code', 'payment_method', 'processor_ref'])
pay['account_id'] = A.aid.values[pay.account_idx.values]
pc = df(O['pc'], ['subscription_id', 'account_idx', 'changed_at', 'change_type', 'from_plan', 'to_plan', 'from_interval', 'to_interval', 'from_seats', 'to_seats', 'mrr_before_usd', 'mrr_after_usd', 'initiated_by'])
pc['account_id'] = A.aid.values[pc.account_idx.values]
