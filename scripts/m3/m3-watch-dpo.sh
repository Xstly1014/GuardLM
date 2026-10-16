#!/usr/bin/env bash
# M3: DPO 训练进度速览（loss 四曲线 + 进程 + 显存）
S=/root/saves/Qwen3-1.7B/guardlm-dpo-v1
echo "---- process ----"
ps aux | grep 'llamafactory-cli train' | grep -v grep | awk '{print $2, $3"%cpu", $10}' || echo "(no process)"
nvidia-smi --query-gpu=memory.used --format=csv,noheader
echo "---- trainer_log (曲线) ----"
python3 - <<'EOF'
import json
path = "/root/saves/Qwen3-1.7B/guardlm-dpo-v1/trainer_log.jsonl"
try:
    rows = [json.loads(l) for l in open(path) if l.strip()]
except FileNotFoundError:
    print("(no trainer_log yet)")
    raise SystemExit
for r in rows:
    if "loss" in r:
        keep = {k: round(v, 4) for k, v in r.items()
                if k in ("loss", "rewards/accuracies", "rewards/margins",
                         "rewards/chosen", "rewards/rejected", "eval_loss",
                         "epoch", "learning_rate")}
        print(r.get("current_step"), keep)
EOF
echo "---- log tail ----"
tail -c 500 /mnt/e/workspace_work/GuardLM/logs/dpo-v1.log
echo
ls $S 2>/dev/null
