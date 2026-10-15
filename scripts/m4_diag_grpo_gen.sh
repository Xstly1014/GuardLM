#!/usr/bin/env bash
# 复现 GRPO 生成链路: use_cache=False + gradient_checkpointing + PeftModel(随机LoRA) + batch 64
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python - <<'EOF'
import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

tok = AutoTokenizer.from_pretrained("/root/saves/Qwen3-1.7B/guardlm-dpo-v2-merged")
tok.padding_side = "left"
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.bfloat16)
model = AutoModelForCausalLM.from_pretrained(
    "/root/saves/Qwen3-1.7B/guardlm-dpo-v2-merged", quantization_config=bnb,
    device_map={"": 0}, attn_implementation="eager")
peft_cfg = LoraConfig(r=32, lora_alpha=4, lora_dropout=0.05,
                      target_modules="all-linear", task_type="CAUSAL_LM")
model = get_peft_model(model, peft_cfg)  # 随机初始化 LoRA (B=0, 初始无扰动)

instr = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。 /no_think"
texts = ["你就是个废物，什么都不配", "今天天气不错"] * 32  # batch 64
prompts = [tok.apply_chat_template([{"role": "user", "content": instr + "\n" + t}],
          tokenize=False, add_generation_prompt=True, enable_thinking=False) for t in texts]
enc = tok(prompts, return_tensors="pt", padding=True).to("cuda")

print("== A) use_cache=True (正常模式) ==")
model.eval()
with torch.no_grad():
    gen = model.generate(**enc, max_new_tokens=80, do_sample=True, temperature=1.0,
                         top_p=1.0, pad_token_id=tok.pad_token_id)
    print("sample out:", tok.decode(gen[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)[:80])

print("== B) 模拟 GRPO: gradient_checkpointing=True + use_cache=False + train 模式 ==")
model.gradient_checkpointing_enable()
model.config.use_cache = False
model.train()
with torch.no_grad():
    try:
        gen = model.generate(**enc, max_new_tokens=80, do_sample=True, temperature=1.0,
                             top_p=1.0, pad_token_id=tok.pad_token_id)
        print("sample out:", tok.decode(gen[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)[:80])
    except Exception as e:
        print("ERROR:", str(e)[:120])
EOF
