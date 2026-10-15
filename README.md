# GuardLM

**A vertical-domain LLM for Chinese content-safety risk detection, trained end-to-end on a single consumer GPU.**

GuardLM ingests one Chinese text (comment, danmaku, or message) and emits a structured, explainable risk verdict:

```json
{
  "label": "insult",
  "risk": 0.95,
  "reason": "文本包含人身攻击性表述"
}
```

Labels: `porn` | `insult` | `ads` | `illegal` | `none`.

The repository covers the complete production path of a content-moderation model: a rule-based adversarial data engine, three-stage alignment training (SFT → DPO → GRPO), a three-tier benchmark harness, and serving with constrained decoding.

## Features

- **Structured output with reason field** — classification, calibrated confidence, and one-line attribution, enforced in JSON for downstream rule engines.
- **Adversarial data engine** — deterministic, parameterized augmentation (variant rewrite, character splitting, homophone substitution) generates attack surfaces beyond public datasets.
- **Three-tier benchmark** — T1 (conventional), T2 (adversarial), T3 (boundary) are dataset-isolated to prevent leakage; a unified harness produces per-tier Markdown reports.
- **Full alignment stack on one GPU** — QLoRA-based SFT/DPO/GRPO for Qwen3-1.7B fits in 24 GB VRAM; the validated pipeline runs at ~4.8 samples/s on an RTX 4090.
- **Serving with constrained decoding** — vLLM serving with JSON-schema constrained output (0.00% format errors), a FastAPI demo with fail-closed error handling, and an AWQ 4-bit option with measured accuracy trade-offs.

## Training Pipeline

```
Public datasets (COLD / CValues / Safety-Prompts)
        │
        ▼
Data engine ── clean, unify schema, adversarial augment, LLM-synthesize
        │
        ▼
SFT ── instruction tuning on classification tasks (QLoRA)
        │
        ▼
DPO ── preference pairs from safe/unsafe answer contrast
        │
        ▼
GRPO ── outcome-rewarded exploration on ambiguous cases
        │
        ▼
Benchmark (T1/T2/T3) + Harness reports ──► vLLM + AWQ serving
```

## Repository Structure

```
data/            raw / interim / sft / rl / cpt / eval — dataset pipeline stages
scripts/         environment setup, training, serving, and verification scripts
training/        per-stage configs and launchers (cpt / sft / dpo / grpo)
harness/         evaluation pipeline (python -m harness.run)
demo/            FastAPI wrapper + web demo page for the vLLM backend
bench/           load-test scripts
configs/         synthesis scenario matrices
review/          human-review worksheets archive
reports/         evaluation reports per model version
experiments.md   experiment log: config / metrics / conclusion per run
```

## Requirements

| Component | Version |
|---|---|
| OS (training) | Ubuntu 22.04 (WSL2 or native) |
| Python | 3.10 |
| PyTorch | 2.5.0 + cu121 |
| Fine-tuning framework | LLaMA-Factory v0.9.3 |
| Quantization | bitsandbytes 0.45.3 (training), AWQ (serving) |
| GPU | ≥ 16 GB VRAM (validated on RTX 4090 24 GB) |

## Quickstart

The training pipeline ships with a sanity-check script that runs QLoRA SFT on the bundled identity dataset, then merges the adapter back into the base model:

```bash
# 1. QLoRA SFT — 230 steps, ~95 s on RTX 4090
bash scripts/m0-8-run-sft-v2.sh

# 2. Merge LoRA into the base model (dequantized bf16 export)
bash scripts/m0-8-merge.sh

# 3. Verify the fine-tune took effect via inference
python scripts/m0-8-chat-verify.py
```

Environment setup scripts (WSL2 provisioning, offline PyTorch install, LLaMA-Factory dependency installation) are under `scripts/` with the `m0-` prefix. Full experiment records, including troubleshooting notes for WSL2/CUDA interop, are in [experiments.md](experiments.md).

## Deployment

The validated production form is the bf16 model (`guardlm-final`) served by vLLM with JSON-schema constrained decoding, which pins the format error rate at 0.00%.

### Start the inference server

```bash
# bf16 (recommended, zero accuracy loss vs. training time)
bash scripts/m6-2-serve.sh

# AWQ 4-bit (low-VRAM option, see trade-off table below)
bash scripts/m6-2-serve.sh guardlm /root/models/guardlm-awq
```

Prefix caching is disabled by default to keep benchmark numbers honest.

### Run the demo API

```bash
uvicorn demo.app:app --host 0.0.0.0 --port 7860
```

The demo wraps the vLLM backend with constrained decoding plus layered parse fallback, and follows a **fail-closed** discipline: when the inference backend is unreachable or a verdict cannot be parsed, it returns an explicit 502 instead of a fabricated verdict.

### Measured capacity (RTX 4090, single GPU, bf16)

| Concurrency | Throughput | P99 E2E latency | TTFT P99 |
|---|---|---|---|
| 1 | 28.2 req/s | 35 ms | 27 ms |
| 4 | 49.5 req/s | 81 ms | 45 ms |
| 16 | 62.3 req/s | 266 ms | 74 ms |

### Quantization trade-off (650-sample benchmark)

| Deployment | F1 | Recall | FPR | Weight size | Eval time |
|---|---|---|---|---|---|
| HF transformers (bf16) | 0.8740 | 0.7824 | 2.86% | 3.3 GiB | ~4.5 min |
| vLLM (bf16) | **0.8755** | 0.7863 | 3.57% | 3.3 GiB | 183 s |
| vLLM (AWQ 4-bit) | 0.8274 | 0.7098 | **2.14%** | **1.3 GiB** | **69 s** |

vLLM bf16 is the recommended form: zero accuracy loss against the training-time baseline plus ~2.4x batch throughput. AWQ 4-bit costs 4.8-pt F1, concentrated in recall on adversarial homophone/split variants, in exchange for 61% smaller weights and 2.6x faster batch inference — keep it for ≤ 8 GB VRAM deployments or offline bulk pre-screening, not as the primary serving path.

## Roadmap

| Stage | Scope | Status |
|---|---|---|
| Environment & pipeline validation | WSL2 + CUDA + LLaMA-Factory, QLoRA SFT closed loop | Done |
| Data engine | COLD/CValues/Safety-Prompts ingestion, adversarial augmentation, LLM synthesis, benchmark sets | Done |
| SFT | Classification instruction tuning (sft-v1, F1 0.862) | Done |
| DPO / GRPO | Preference optimization + outcome-rewarded RL (dpo-v2, grpo-v1, F1 0.874) | Done |
| CPT ablation | Domain continued pre-training vs. direct SFT (sft-v2) | Done (ablation; production keeps grpo-v1) |
| Benchmark & harness | T1/T2/T3 evaluation, per-version reports | Done |
| Serving | vLLM bf16 + constrained decoding, load tests, demo API, AWQ trade-off | Done |

## Acknowledgements

- [COLD](https://github.com/thu-coai/COLD) (THUPLab) — offensiveness-annotated Chinese corpus
- [CValues](https://github.com/X-PLUG/CValues) (Alibaba) — safety-contrast QA pairs
- [Safety-Prompts](https://github.com/thu-coai/Safety-Prompts) (Thu-CoAI) — adversarial safety scenarios
- [Qwen3](https://github.com/QwenLM/Qwen3) — base model
- [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) — fine-tuning framework
- [vLLM](https://github.com/vllm-project/vllm) — inference serving

## License

This project is licensed under the [MIT License](LICENSE).
