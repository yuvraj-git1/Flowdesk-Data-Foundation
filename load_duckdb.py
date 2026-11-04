"""Stage 6: load CSVs into DuckDB and validate.  Usage: python load_duckdb.py   (needs `pip install duckdb`)"""
import duckdb, pathlib
from schema import TABLES
ROOT = pathlib.Path(__file__).resolve().parent
db = ROOT / "flowdesk.duckdb"
db.unlink(missing_ok=True)   # idempotent rebuild
con = duckdb.connect(str(db))
con.execute((ROOT / "sql/01_schema.sql").read_text())
for t in TABLES:
    csv = (ROOT / "data" / "csv" / f"{t.name}.csv").as_posix()
    con.execute(f"INSERT INTO {t.qname} SELECT * FROM read_csv_auto('{csv}', header=true, sample_size=-1)")
print("rows:", {t.name: con.execute(f"select count(*) from {t.qname}").fetchone()[0] for t in TABLES})

def q(sql): return con.execute(sql).fetchall()
fails = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name, detail); (not ok) and fails.append(name)

# 1) referential integrity (declared FKs, not enforced by DDL)
for t in TABLES:
    for c in t.cols:
        if c.fk:
            pt, pc = c.fk.split("."); ptab = next(x.qname for x in TABLES if x.name == pt)
            n = q(f"select count(*) from {t.qname} a left join {ptab} b on a.{c.name}=b.{pc} where a.{c.name} is not null and b.{pc} is null")[0][0]
            check(f"FK {t.name}.{c.name}->{c.fk}", n == 0, f"orphans={n}")
# 2) headline calibration
signups = q("select count(*) from accounts")[0][0]; check("signups ~40K", 38000 <= signups <= 42000, signups)
ever = q("select count(*) from accounts where first_paid_at is not null")[0][0]; check("ever-paid ~4K", 3600 <= ever <= 4600, ever)
arr = q("select sum(mrr_usd)*12 from subscriptions")[0][0]; check("ARR ~$6M", 5.5e6 <= arr <= 6.5e6, round(arr))
ss = q("select avg((acquisition_motion='sales_assisted')::int) from accounts where first_paid_at is not null")[0][0]; check("sales-assisted ~15% of paid", .12 <= ss <= .18, round(ss, 3))
ev = q("select count(*) from events")[0][0]; check("events 3-4M", 3e6 <= ev <= 4e6, ev)
pf = q("select avg((status='failed')::int) from payments where attempt_number=1")[0][0]; check("payment failure ~4%", .035 <= pf <= .047, round(pf, 4))
# 3) growth then stall: MRR by month-end from plan_changes
m = q("""with d as (select date_trunc('month',changed_at) mth, sum(mrr_after_usd-mrr_before_usd) dm from plan_changes group by 1)
         select mth, sum(dm) over (order by mth) mrr from d order by mth""")
d = {str(r[0])[:7]: r[1] for r in m}; g24 = d["2024-12"] / d["2023-12"]; g25 = d["2025-12"] / d["2024-12"]
check("MRR grew strongly in 2024, stalled in 2025", g24 > 1.5 and g25 < 1.15, f"2024x{g24:.2f} 2025x{g25:.2f}")
# 4) behaviour logic: activation, aha, retention (owners, matured)
r = q("""with o as (select user_id, created_at from users where role='owner' and created_at < timestamp '2025-09-20'),
 e as (select o.user_id, e.event_name, epoch(e.event_ts-o.created_at)/86400.0 d from o join events e using(user_id))
 select avg(aha::int), avg(case when aha then ret::int end), avg(case when not aha then ret::int end) from (
  select o.user_id, exists(select 1 from e where e.user_id=o.user_id and event_name='teammate_invited' and d<=3) aha,
         exists(select 1 from e where e.user_id=o.user_id and d between 84 and 98) ret from o)""")[0]
check("aha 12w retention ~55% vs ~20%", .48 <= r[1] <= .62 and .15 <= r[2] <= .28, f"aha={r[1]:.3f} non-aha={r[2]:.3f}")
# 5) planted problems recovered exactly via _truth
ak = {x[0]: x for x in q("select problem_id, affected_row_count from _truth.answer_key")}
b4 = q("select count(*) from _truth.planted_rows where problem_id='B4' and role='duplicate'")[0][0]; check("B4 dups recoverable", b4 == ak["B4"][1], b4)
b3 = q("select count(distinct account_id) from seat_usage_monthly where seats_provisioned>seats_billed and seats_billed>0")[0][0]; check("B3 unbilled-SSO accounts detectable", b3 >= ak["B3"][1] * .9, f"{b3} vs {ak['B3'][1]}")
b7 = q("select count(*) from (select payment_id from refunds group by 1 having count(*)>1)")[0][0]; check("B7 duplicate refunds detectable", b7 == ak["B7"][1], b7)
p5 = q("select count(*) from (select user_id, task_id from events where task_id is not null group by 1,2 having count(*)>1)")[0][0]; check("P5 double-fires detectable", p5 == ak["P5"][1], p5)
srm = q("select avg((variant='treatment')::int) from experiment_assignments where experiment_id=3")[0][0]; check("P2 SRM ~47.7% treatment", .46 <= srm <= .49, round(srm, 3))
print("\nALL CHECKS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
