#!/bin/bash
# 确认 grpo-v1 adapter 的挂载基座
echo "=== grpo-v1 adapter_config.json ==="
python3 -c "import json; c=json.load(open('/root/saves/Qwen3-1.7B/guardlm-grpo-v1/adapter_config.json')); print('base_model:', c.get('base_model_name_or_path'))"
echo "=== dpo-v2 adapter_config.json ==="
python3 -c "import json; c=json.load(open('/root/saves/Qwen3-1.7B/guardlm-dpo-v2/adapter_config.json')); print('base_model:', c.get('base_model_name_or_path'))"
echo "=== sft-v1 adapter_config.json ==="
python3 -c "import json; c=json.load(open('/root/saves/Qwen3-1.7B/guardlm-sft-v1/adapter_config.json')); print('base_model:', c.get('base_model_name_or_path'))"
echo "=== LLaMA-Factory grpo yaml ==="
ls /root/LLaMA-Factory/*.yaml 2>/dev/null | tail -10
grep -E "model_name_or_path|adapter" /root/LLaMA-Factory/grpo*.yaml 2>/dev/null
