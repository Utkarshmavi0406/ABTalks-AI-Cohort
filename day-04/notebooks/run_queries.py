import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "coverage.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

def run(title, sql):
    print(f"\n{title}")
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    for row in cur.fetchall():
        print(" | ".join(str(v) for v in row))



run("Q1: Deductible on Gold PPO", """
    SELECT plan_name, annual_deductible
    FROM plans
    WHERE plan_name = 'Gold PPO';
""")

run("Q2: Pending claim count for M1001", """
    SELECT COUNT(*) AS pending_count
    FROM claims
    WHERE member_id = 'M1001' AND status = 'Pending';
""")


run("Q3: Plans with monthly premium under $400", """
    SELECT plan_name, monthly_premium
    FROM plans
    WHERE monthly_premium < 400
    ORDER BY monthly_premium;
""")


run("Q4: Claims with plan details (JOIN)", """
    SELECT c.claim_id, c.member_id, c.procedure, c.claim_amount, c.status, p.plan_name, p.network_tier
    FROM claims c
    JOIN plans p ON c.plan_id = p.plan_id
    ORDER BY c.claim_id;
""")

run("Q5: Top procedures by claim count", """
    SELECT procedure, COUNT(*) AS claim_count, SUM(claim_amount) AS total_claimed
    FROM claims
    GROUP BY procedure
    ORDER BY claim_count DESC, total_claimed DESC
    LIMIT 5;
""")


