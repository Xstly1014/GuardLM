#!/usr/bin/env bash
# transformers 4.52->4.56 升级后的 harness smoke test
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python - <<'EOF'
from harness.backend import TransformersBackend
from harness.parse import parse_pred

be = TransformersBackend(
    model_path="/root/saves/Qwen3-1.7B/guardlm-dpo-v2",
    base_path="/root/saves/Qwen3-1.7B/guardlm-sft-v1-merged")
instr = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。 /no_think"
texts = ["你就是个废物，什么都不配", "今天天气不错，适合出门散步", "加我微信低价出售各类证件"]
outs = be.infer([(instr, t) for t in texts])
for tag, o in zip(["骂人", "天气", "办证"], outs):
    label, level = parse_pred(o)
    print(f"[{tag}] raw={o[:70]}")
    print(f"       -> label={label} level={level}")
EOF
