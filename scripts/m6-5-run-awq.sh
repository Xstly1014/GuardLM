#!/usr/bin/env bash
# M6-5: AWQ 量化执行器（显存已释放后）
set -euo pipefail
echo "=== VRAM 状态 ==="
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
echo "=== autoawq 可用性 ==="
/root/serve-venv/bin/python - <<'PY'
import awq
print("autoawq import OK", getattr(awq, "__version__", "?"))
PY
echo "=== 开始量化（校准 128 条评测集 prompt）==="
/root/serve-venv/bin/python /mnt/e/workspace_work/GuardLM/scripts/awq_quant.py \
  --model /root/models/guardlm-final --out /root/models/guardlm-awq
echo "=== bf16 vs awq 体积对比 ==="
du -sh /root/models/guardlm-final /root/models/guardlm-awq
echo "AWQ_QUANT_DONE"
