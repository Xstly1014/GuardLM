#!/bin/bash
# M0-8: merge QLoRA adapter into base model (dequantized bf16), then verify by chat.
set -e
source /root/guardlm-venv/bin/activate
export HF_HUB_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
cd /root/LLaMA-Factory

echo "[1/2] Exporting merged model (base bf16 + LoRA adapter, dequantized)..."
llamafactory-cli export \
  --model_name_or_path /root/models/Qwen3-1.7B \
  --adapter_name_or_path /root/saves/Qwen3-1.7B/qwen3-qlora-sft-m0-v2 \
  --template qwen3 \
  --export_dir /root/models/Qwen3-1.7B-sft-m0-v2-merged \
  --export_size 5 \
  --export_legacy_format false

echo "[2/2] Merged model files:"
ls -la /root/models/Qwen3-1.7B-sft-m0-v2-merged/
echo "M0-8 EXPORT DONE"
