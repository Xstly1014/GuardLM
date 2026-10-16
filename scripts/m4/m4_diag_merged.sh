#!/usr/bin/env bash
# 诊断: dpo-v2-merged 合并权重在 4bit + 温度1.0 下是否还能正常输出
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python - <<'EOF'
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

tok = AutoTokenizer.from_pretrained("/root/saves/Qwen3-1.7B/guardlm-dpo-v2-merged")
tok.padding_side = "left"
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.bfloat16)
model = AutoModelForCausalLM.from_pretrained(
    "/root/saves/Qwen3-1.7B/guardlm-dpo-v2-merged", quantization_config=bnb,
    device_map={"": 0}, attn_implementation="eager").eval()

instr = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。 /no_think"
texts = ["你就是个废物，什么都不配", "今天天气不错，适合出门散步"]
prompts = [tok.apply_chat_template([{"role": "user", "content": instr + "\n" + t}],
          tokenize=False, add_generation_prompt=True, enable_thinking=False) for t in texts]
enc = tok(prompts, return_tensors="pt", padding=True).to("cuda")

for temp in (1.0, 0.7):
    gen = model.generate(**enc, max_new_tokens=80, do_sample=True,
                         temperature=temp, top_p=1.0, pad_token_id=tok.pad_token_id)
    for j, t in enumerate(texts):
        out = tok.decode(gen[j][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        print(f"[temp={temp}] {t[:12]}... -> {out[:90]}")
    print()
EOF
