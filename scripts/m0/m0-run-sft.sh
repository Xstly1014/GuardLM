#!/bin/bash
# M0-7: Official quickstart-style QLoRA SFT on identity dataset.
# Model: Qwen3-1.7B (local), 4-bit bnb quant, LoRA on all linear layers.
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
  --output_dir /root/saves/Qwen3-1.7B/qwen3-qlora-sft-m0 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 2 \
  --learning_rate 5e-5 \
  --num_train_epochs 1.0 \
  --max_samples 500 \
  --cutoff_len 1024 \
  --lr_scheduler_type cosine \
  --warmup_ratio 0.1 \
  --max_grad_norm 1.0 \
  --logging_steps 5 \
  --save_steps 100 \
  --plot_loss true \
  --bf16 true \
  --report_to none

echo "=== TRAIN DONE, artifacts: ==="
ls -la /root/saves/Qwen3-1.7B/qwen3-qlora-sft-m0/
echo "M0-7 DONE"
