# Structured Queries — Day 4

Five SQL queries run against `coverage.db`, each mapped to a realistic
member question. Run via `notebooks/run_queries.py`.

---

## Q1 — What's the deductible on the Gold PPO plan?

```sql
SELECT plan_name, annual_deductible
FROM plans
WHERE plan_name = 'Gold PPO';
```

**Output:**
```
plan_name | annual_deductible
Gold PPO | 2000

```

---

## Q2 — How many claims are pending for member M1001?

```sql
SELECT COUNT(*) AS pending_count
FROM claims
WHERE member_id = 'M1001' AND status = 'Pending';
```

**Output:**
```
pending_count
1

```

---

## Q3 — Which plans have a monthly premium under $400?

```sql
SELECT plan_name, monthly_premium
FROM plans
WHERE monthly_premium < 400
ORDER BY monthly_premium;
```

**Output:**
```
plan_name | monthly_premium
Bronze HMO | 150
Silver HMO | 300

```

---

## Q4 — Claims with plan details (JOIN)

```sql
SELECT c.claim_id, c.member_id, c.procedure, c.claim_amount, c.status, p.plan_name, p.network_tier
FROM claims c
JOIN plans p ON c.plan_id = p.plan_id
ORDER BY c.claim_id;
```

**Output:**
```
claim_id | member_id | procedure | claim_amount | status | plan_name | network_tier
C1001 | M1001 | X-ray | 250 | Pending | Gold PPO | Gold
C1002 | M1001 | Surgery | 1200 | Approved | Gold PPO | Gold
C1003 | M1002 | X-ray | 150 | Denied | Silver HMO | Silver
C1004 | M1002 | Surgery | 900 | Approved | Silver HMO | Silver
C1005 | M1003 | X-ray | 50 | Pending | Bronze HMO | Bronze

```

---

## Q5 — Top procedures by claim count (top-N)

```sql
SELECT procedure, COUNT(*) AS claim_count, SUM(claim_amount) AS total_claimed
FROM claims
GROUP BY procedure
ORDER BY claim_count DESC, total_claimed DESC
LIMIT 5;
```

**Output:**
```
procedure | claim_count | total_claimed
X-ray | 3 | 450
Surgery | 2 | 2100

```
