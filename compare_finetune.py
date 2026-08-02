"""
Day 15 — Base vs Fine-Tuned Comparison
Runs the 5 Day 14 held-out test questions through both the base model
and the LoRA fine-tuned model, for side-by-side scoring.
"""

import json
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_DIR = "adapters/qwen2.5-0.5b-coverage-lora"
TEST_FILE = "fine_tune_test.jsonl"

if torch.backends.mps.is_available():
    device = "mps"
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"
print(f"Using device: {device}")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

print("Loading base model...")
base_model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.float32).to(device)

print("Loading fine-tuned (LoRA) model...")
finetuned_model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
# Note: PeftModel wraps the same base weights + adapter; we reload the base
# separately below so comparing the two doesn't share mutated state.
base_model_fresh = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.float32).to(device)


def generate(model, question: str, system_prompt: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=150,
            do_sample=False,
            temperature=None,
            top_p=None,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )

    generated = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


if __name__ == "__main__":
    # Load the 5 held-out questions (and their system prompt) from Day 14's test set
    test_examples = []
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            messages = record["messages"]
            system_content = next(m["content"] for m in messages if m["role"] == "system")
            user_content = next(m["content"] for m in messages if m["role"] == "user")
            expected = next(m["content"] for m in messages if m["role"] == "assistant")
            test_examples.append({"system": system_content, "question": user_content, "expected": expected})

    print(f"\nLoaded {len(test_examples)} held-out test questions\n")

    results = []
    for ex in test_examples:
        print(f"{'='*80}\nQ: {ex['question']}")
        print(f"(expected/reference answer: {ex['expected']})\n")

        base_answer = generate(base_model_fresh, ex["question"], ex["system"])
        print(f"BASE MODEL:\n{base_answer}\n")

        ft_answer = generate(finetuned_model, ex["question"], ex["system"])
        print(f"FINE-TUNED MODEL:\n{ft_answer}\n")

        results.append({
            "question": ex["question"],
            "expected": ex["expected"],
            "base_answer": base_answer,
            "finetuned_answer": ft_answer,
        })

    with open("fine_tune_eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved comparison results to fine_tune_eval_results.json")
