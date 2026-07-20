import sqlite3
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = Path(__file__).resolve().parent.parent / "coverage.db"

plans = pd.read_csv(DATA_DIR / "plans.csv")
claims = pd.read_csv(DATA_DIR / "claims.csv")

print("=== plans.info() ===")
plans.info()

print("\n=== plans.head() ===")
print(plans.head())

print("\n=== claims.info() ===")
claims.info()
print("\n=== claims.head() ===")
print(claims.head())

print("\n=== Duplicate check ===")
print("plans duplicates:", plans.duplicated().sum())
print("claims duplicates:", claims.duplicated().sum())

plans = plans.drop_duplicates(subset="plan_id", keep="first")
claims = claims.drop_duplicates(subset="claim_id", keep="first")


print("\n=== Null check ===")
print("plans nulls:\n", plans.isnull().sum())
print("claims nulls:\n", claims.isnull().sum())

# Drop rows missing any required numeric field — unusable for cost calcs
plans = plans.dropna(subset=["plan_id", "monthly_premium", "annual_deductible", "copay_pct"])
claims = claims.dropna(subset=["claim_id", "member_id", "plan_id", "claim_amount"])

claims["date_filed"] = pd.to_datetime(claims["date_filed"], errors="coerce")

print("\n=== claims.info() after cleaning ===")
claims.info()


plans["monthly_premium"] = pd.to_numeric(plans["monthly_premium"], errors="coerce")
plans["annual_deductible"] = pd.to_numeric(plans["annual_deductible"], errors="coerce")
plans["copay_pct"] = pd.to_numeric(plans["copay_pct"], errors="coerce")

claims["claim_amount"] = pd.to_numeric(claims["claim_amount"], errors="coerce")

print("\n=== Final cleaned plans ===")
print(plans.dtypes)
print(plans)

print("\n=== Final cleaned claims ===")
print(claims.dtypes)
print(claims)

print("\n=== Loading into SQLite ===")
conn = sqlite3.connect(DB_PATH)

plans.to_sql("plans", conn, if_exists="replace", index=False)
claims.to_sql("claims", conn, if_exists="replace", index=False)

conn.commit()
conn.close()

verify_conn = sqlite3.connect(DB_PATH)
cur = verify_conn.cursor()
cur.execute("SELECT COUNT(*) FROM plans")
print("plans row count in db:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM claims")
print("claims row count in db:", cur.fetchone()[0])
verify_conn.close()


print(f"Loaded 'plans' ({len(plans)} rows) and 'claims' ({len(claims)} rows) into {DB_PATH}")