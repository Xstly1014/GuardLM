#!/bin/bash
# M0-8: stronger identity SFT so the effect is observable over Qwen's
# pre-trained self-identification (5 epochs, lr 1e-4, patched identity data).
set -e
source /root/guardlm-venv/bin/activate
export HF_HUB_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
cd /root/LLaMA-Factory

llamafactory-cli train \
  --stage sft \
  --do_train \
  --model_name_or_path /root/models/Qwen3-1.7B \
  --dataset identity \
  --dataset_dir /root/LLaMA-Factory/data \
  --template qwen3 \
  --finetuning_type lora \
  --lora_target all \
  --quantization_bit 4 \
  --output_dir /root/saves/Qwen3-1.7B/qwen3-qlora-sft-m0-v2 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 2 \
  --learning_rate 1e-4 \
  --num_train_epochs 5.0 \
  --max_samples 500 \
  --cutoff_len 1024 \
  --lr_scheduler_type cosine \
  --warmup_ratio 0.1 \
  --max_grad_norm 1.0 \
  --logging_steps 10 \
  --save_steps 500 \
  --plot_loss true \
  --bf16 true \
  --report_to none

echo "=== TRAIN DONE ==="
tail -3 /root/saves/Qwen3-1.7B/qwen3-qlora-sft-m0-v2/trainer_log.jsonl
echo "M0-8 SFT-V2 DONE"
