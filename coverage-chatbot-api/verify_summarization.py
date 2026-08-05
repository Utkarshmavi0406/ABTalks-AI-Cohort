"""
verify_summarization.py
Day 20 — standalone proof that maybe_summarize() actually triggers and
works correctly, without needing to manually send 50+ chat messages
through the UI to organically cross the 2000-token threshold.

Run from Daily Task root:
    cd coverage-chatbot-api
    python3 verify_summarization.py
"""

import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from main import init_db, save_turn, load_history, maybe_summarize, DB_PATH, count_tokens

TEST_SESSION = "summarization-verification-test"

# Clean up any prior run of this test
conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM conversations WHERE session_id = ?", (TEST_SESSION,))
conn.commit()
conn.close()

init_db()

# Build a synthetic long conversation -- long enough to comfortably exceed
# 2000 tokens, so we can verify the real summarize_turns() LLM call and the
# real replace_turns_with_summary() DB logic, without 50+ manual UI turns.
sample_qa_pairs = [
    ("I'm on the Gold PPO plan. What's my copay?", "Your copay for the Gold PPO plan is 10%."),
    ("What's the status of claim C1001?", "The status of claim C1001 is Pending. The procedure is an X-ray, and the amount is $250."),
    ("Is cosmetic surgery excluded from coverage?", "Yes, cosmetic surgery is excluded from coverage under your Gold PPO plan, as explicitly stated in the exclusions section of the policy document."),
    ("How much is the deductible?", "The deductible for the Gold PPO plan is $2000 per year, which is the amount you pay out of pocket before your insurance starts sharing costs."),
    ("What about the premium?", "The premium for the Gold PPO plan is $500 per month, which is what you pay to keep your coverage active regardless of usage."),
    ("Is dental care covered for adults?", "Dental care for adults is excluded from coverage under the Gold PPO plan, as stated in the policy's list of excluded services."),
    ("What's the status of claim C1003?", "The status of claim C1003 is Denied. This claim was for an X-ray procedure with an amount of $150."),
    ("Does my plan cover routine eye care?", "Routine eye care for adults is excluded from coverage under the Gold PPO plan, as stated in the policy exclusions section."),
    ("What's my out-of-pocket cost for an X-ray?", "Based on your plan's copay structure, your estimated out-of-pocket cost for a standard X-ray would be calculated using the 10% copay rate."),
    ("Is physical therapy covered?", "Physical therapy is not explicitly listed as an excluded service under the Gold PPO plan, though specific limitations may apply."),
]
# Repeat the set to comfortably exceed the token budget.
# (1026 tokens for x3 repeats in initial testing meant ~342 tokens/repeat --
# x7 gives a healthy margin above the 2000-token threshold.)
sample_qa_pairs = sample_qa_pairs * 7

for question, answer in sample_qa_pairs:
    save_turn(TEST_SESSION, "user", question)
    save_turn(TEST_SESSION, "assistant", answer)

history = load_history(TEST_SESSION)
full_text = "\n".join(t["content"] for t in history)
built_tokens = count_tokens(full_text)
print(f"Synthetic conversation built: {len(history)} turns, {built_tokens} tokens (real tiktoken count)")

from main import TOKEN_BUDGET
print(f"Token budget: {TOKEN_BUDGET}")
if built_tokens <= TOKEN_BUDGET:
    print(f"WARNING: built conversation ({built_tokens} tokens) does not exceed the budget "
          f"({TOKEN_BUDGET}) -- summarization will correctly NOT trigger. Increase the repeat "
          f"count above and re-run if you want to see it actually fire.")

print("\nCalling maybe_summarize() -- this makes one real LLM call to summarize the oldest half...\n")

new_history, tokens_before, tokens_after = maybe_summarize(TEST_SESSION, history)

print(f"\nResult:")
print(f"  tokens_before = {tokens_before}")
print(f"  tokens_after  = {tokens_after}")
print(f"  turns_before  = {len(history)}")
print(f"  turns_after   = {len(new_history)}")
print(f"\nFirst entry in trimmed history (should be role='summary'):")
print(f"  role: {new_history[0]['role']}")
print(f"  content: {new_history[0]['content']}")

assert tokens_after < tokens_before, "Summarization did not reduce token count!"
assert new_history[0]["role"] == "summary", "First entry should be the summary!"
print("\n✅ Summarization confirmed working: token count reduced and summary correctly placed first.")

# Clean up the test session afterward
conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM conversations WHERE session_id = ?", (TEST_SESSION,))
conn.commit()
conn.close()
