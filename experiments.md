# GuardLM 实验日志（experiments.md）

> 纪律：训练前写入计划，训练后立刻补结果与结论。**没有报告的实验等于没做。**
> 所有对外引用的指标必须能追溯到本文件的某条记录。

---

## EXP-000 | M0 环境验证：QLoRA SFT quickstart 跑通（qwen3-qlora-sft-m0 / m0-v2）

- **日期**：2026-10-15
- **目的**：验证本地 RTX 4090（WSL2）训练链路全通：数据 → QLoRA SFT → LoRA 合并 → 推理验证
- **基座**：Qwen3-1.7B（bf16，本地路径 `/root/models/Qwen3-1.7B`，WSL2 内）
- **框架**：LLaMA-Factory v0.9.3 + PyTorch 2.5.0+cu121 + bitsandbytes 0.45.3（Python 3.10 venv）
- **数据**：LLaMA-Factory `identity` 数据集（91 条），占位符替换为 `{{name}}→GuardLM`、`{{author}}→郭剑华`

### 训练配置（v2，最终生效版）

| 参数 | 值 |
|---|---|
| finetuning | QLoRA（LoRA r=8, alpha=16, all-linear, dropout=0）+ 4bit bnb 量化 |
| lr / scheduler | 1e-4 / cosine, warmup 0.1 |
| epochs | 5.0（230 steps） |
| batch | 1 × grad_accum 2 = 有效 2 |
| cutoff_len | 1024 |
| precision | bf16 |
| 可训练参数 | 8.7M / 1.73B = 0.50% |

### 结果

| 版本 | 配置差异 | loss 曲线 | 耗时 | 对话验证 |
|---|---|---|---|---|
| m0 | 1 epoch, lr 5e-5 | 4.49 → 1.62（46 步） | 25s | ✗ 仍自称 Alibaba（基座先验未覆盖） |
| **m0-v2** | **5 epochs, lr 1e-4** | **4.49 → 0.33（230 步），avg 1.03** | **95s** | ✓ 自我认知改写为 GuardLM/郭剑华（中英文均生效） |

v2 合并后对话实测：
- "Who are you?" → "I am GuardLM, an AI assistant trained by 郭剑华."
- "你是谁？" → "您好，我是 GuardLM，一个由 郭剑华 开发的人工智能助手。"

### 产物

- adapter：`/root/saves/Qwen3-1.7B/qwen3-qlora-sft-m0-v2`（34MB）
- 合并模型：`/root/models/Qwen3-1.7B-sft-m0-v2-merged`（bf16 全量 3.4GB）
- 复现脚本：`scripts/m0-run-sft.sh`（v1 配置）、`scripts/m0-8-run-sft-v2.sh`（v2 配置）、`scripts/m0-8-merge.sh`、`scripts/m0-8-chat-verify.py`

### 结论

1. **M0 验收通过**：本地 24G 单卡可完成 Qwen3-1.7B QLoRA 全链路，训练吞吐约 4.8 samples/s，无显存压力（峰值远低于 24G）
2. **Qwen3 基座自我认知先验强**：字面占位符 + 1 epoch（46 步）不足以覆盖；替换占位符为具体名称 + 5 epochs + lr 1e-4 后完全改写——后续 SFT 数据需注意类目先验对短训的影响
3. 带出的环境坑（已修复，见下）在 M1+ 长训中不会再出现

### 排障记录（M0 环境关键坑，供后续参考）

- **现象**：训练第一步前向即崩，`cuDNN Frontend error: No execution plans support the graph`，伴随 `Could not load library libcuda.so`
- **根因**：训练时带 4D padding mask 的 SDPA 会走 cuDNN attention backend，cuDNN frontend JIT 编译执行计划需要 dlopen 无版本号 `libcuda.so` 与 `libnvrtc.so.12`，而 WSL2 的驱动 stub 只提供 `libcuda.so.1`，venv 内的 nvrtc 又不在系统搜索路径
- **修复**（一次操作永久生效）：
  ```bash
  ln -sf /usr/lib/wsl/lib/libcuda.so.1 /usr/lib/x86_64-linux-gnu/libcuda.so
  ln -sf $VENV/site-packages/nvidia/cuda_nvrtc/lib/libnvrtc.so.12 /usr/lib/x86_64-linux-gnu/
  ln -sf $VENV/site-packages/nvidia/nvjitlink/lib/libnvJitLink.so.12 /usr/lib/x86_64-linux-gnu/
  ldconfig
  ```
- **教训**：WSL2 训练环境遇到 cuDNN JIT / "No execution plans" 类报错，先怀疑 dlopen 链不完整（`lsof` / `ldconfig -p` 查库），而非版本不兼容

---
