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

The repository covers the complete production path of a content-moderation model: a rule-based adversarial data engine, three-stage alignment training (SFT → DPO → GRPO), a three-tier benchmark harness, and quantized serving.

## Features

- **Structured output with reason field** — classification, calibrated confidence, and one-line attribution, enforced in JSON for downstream rule engines.
- **Adversarial data engine** — deterministic, parameterized augmentation (variant rewrite, character splitting, homophone substitution) generates attack surfaces beyond public datasets.
- **Three-tier benchmark** — T1 (conventional), T2 (adversarial), T3 (boundary) are dataset-isolated to prevent leakage; a unified harness produces per-tier Markdown reports.
- **Full alignment stack on one GPU** — QLoRA-based SFT/DPO/GRPO for Qwen3-1.7B fits in 24 GB VRAM; the validated pipeline runs at ~4.8 samples/s on an RTX 4090.
- **Quantized deployment** — AWQ 4-bit weights served via vLLM, with a load-test suite to measure throughput and latency.

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
scripts/         environment setup, training, and verification scripts
training/        per-stage configs and launchers (cpt / sft / dpo / grpo)
harness/         evaluation pipeline (python -m harness.run)
serving/         vLLM deployment, quantization, API demo
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

## Roadmap

| Stage | Scope | Status |
|---|---|---|
| Environment & pipeline validation | WSL2 + CUDA + LLaMA-Factory, QLoRA SFT closed loop | Done |
| Data engine | COLD/CValues/Safety-Prompts ingestion, adversarial augmentation, benchmark sets | In progress |
| SFT | Classification instruction tuning, sft-v1 | Planned |
| DPO / GRPO | Preference optimization, outcome-rewarded exploration | Planned |
| Benchmark & harness | T1/T2/T3 evaluation, per-version reports | Planned |
| Serving | vLLM + AWQ 4-bit, load tests, API demo | Planned |

## Acknowledgements

- [COLD](https://github.com/thu-coai/COLD) (THUPLab) — offensiveness-annotated Chinese corpus
- [CValues](https://github.com/X-PLUG/CValues) (Alibaba) — safety-contrast QA pairs
- [Safety-Prompts](https://github.com/thu-coai/Safety-Prompts) (Thu-CoAI) — adversarial safety scenarios
- [Qwen3](https://github.com/QwenLM/Qwen3) — base model
- [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) — fine-tuning framework
- [vLLM](https://github.com/vllm-project/vllm) — inference serving

## License

This project is licensed under the [MIT License](LICENSE).
