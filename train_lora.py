"""
Day 15 — Fine-Tuning Hands-On with LoRA
Fine-tunes a small local model (Qwen2.5-0.5B-Instruct) on the Day 14 training
set using LoRA, running on Apple Silicon's MPS backend.
"""

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
TRAIN_FILE = "fine_tune_train.jsonl"
OUTPUT_DIR = "adapters/qwen2.5-0.5b-coverage-lora"

# ---------- device detection ----------
if torch.backends.mps.is_available():
    device = "mps"
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"
print(f"Using device: {device}")

# ---------- load base model + tokenizer ----------
print(f"Loading base model: {MODEL_NAME}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.float32)
model.to(device)

# ---------- load Day 14 training data ----------
dataset = load_dataset("json", data_files=TRAIN_FILE, split="train")
print(f"Loaded {len(dataset)} training examples")

# ---------- LoRA config ----------
# Small rank since the dataset is tiny (25 examples) — a high-capacity adapter
# would just memorize rather than generalize the tone/pattern we want.
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    task_type="CAUSAL_LM",
)

# ---------- training config ----------
sft_config = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=2,
    learning_rate=2e-4,
    logging_steps=1,
    save_strategy="epoch",
    report_to="none",
    bf16=False,   # MPS doesn't reliably support bf16; keep fp32
    fp16=False,
)

trainer = SFTTrainer(
    model=model,
    args=sft_config,
    train_dataset=dataset,
    peft_config=lora_config,
)

# ---------- Step 2: run + monitor ----------
print("\nStarting training...\n")
trainer.train()

# ---------- save the adapter ----------
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"\nSaved LoRA adapter to {OUTPUT_DIR}")
