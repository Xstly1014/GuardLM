#!/usr/bin/env bash
# M5-2: CPT 训练前检查（数据集注册 + 语料统计 + GPU 状态）
set -e

echo "=== 1. dataset_info.json 注册检查 ==="
if grep -q '"guardlm_cpt"' /root/LLaMA-Factory/data/dataset_info.json; then
    echo "guardlm_cpt: REGISTERED"
    python3 - <<'EOF'
import json
with open('/root/LLaMA-Factory/data/dataset_info.json') as f:
    info = json.load(f)
print(json.dumps(info['guardlm_cpt'], ensure_ascii=False))
EOF
else
    echo "guardlm_cpt: NOT FOUND, running register script..."
    bash /mnt/e/workspace_work/GuardLM/scripts/m5/m5_register_cpt.sh
fi

echo ""
echo "=== 2. 语料统计 ==="
cat /mnt/e/workspace_work/GuardLM/data/cpt/corpus_stats.json

echo ""
echo "=== 3. GPU 状态 ==="
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader

echo ""
echo "=== 4. 上次基座通用探针结果（防遗忘基线）==="
cat /mnt/e/workspace_work/GuardLM/data/cpt/probe_base.json
