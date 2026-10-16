"""M0-8: non-interactive chat verification of the merged SFT model.

Ask identity questions, expect the model to answer with the identity-dataset
pattern (contains '{{name}}' / '{{author}}' placeholders, trained literally),
proving the fine-tune took effect. Also compare against the raw base model.
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MERGED = "/root/models/Qwen3-1.7B-sft-m0-v2-merged"
QUESTIONS = ["Who are you?", "你是谁？", "hi"]

tok = AutoTokenizer.from_pretrained(MERGED)
model = AutoModelForCausalLM.from_pretrained(MERGED, torch_dtype=torch.bfloat16, device_map="cuda")
model.eval()

for q in QUESTIONS:
    messages = [{"role": "user", "content": q}]
    text = tok.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    inputs = tok(text, return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=64,
            do_sample=False,
            pad_token_id=tok.pad_token_id or tok.eos_token_id,
        )
    reply = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    print(f"\nUSER: {q}\nMODEL: {reply}")

print("\nM0-8 CHAT VERIFY DONE")
