# GuardLM

A vertical-domain risk-identification model for Chinese content safety, trained end-to-end on a single consumer GPU: Qwen3-1.7B fine-tuned on an RTX 4090 (24 GB) via the full alignment stack (SFT → DPO → GRPO) and served with vLLM.

## Overview

GuardLM classifies one Chinese text (comment, danmaku, or private message) into five labels — `porn` | `insult` | `ads` | `illegal` | `none` — and emits a structured, machine-parseable verdict:

```json
{
  "label": "insult",
  "risk": 0.95,
  "reason": "文本包含人身攻击性表述"
}
```

The repository covers the complete production path of a content-moderation model:

- **Adversarial data engine** — three public corpora (COLD / CValues / Safety-Prompts) unified at the 120k-text scale, LLM-directed synthesis for scarce risk categories, and deterministic augmentation (homophone, pinyin, character splitting, emoji, traditional Chinese) that reproduces real-world evasion tactics.
- **Three-tier benchmark** — T1 (conventional), T2 (adversarial), T3 (boundary), dataset-isolated with MinHash deduplication and provenance tracking; zero train–eval leakage verified.
- **Full alignment stack on one GPU** — QLoRA-based SFT, DPO, and GRPO for Qwen3-1.7B within 24 GB VRAM.
- **Serving with constrained decoding** — vLLM serving with JSON-schema constrained output, a fail-closed FastAPI demo, and a measured AWQ 4-bit trade-off.

A complete technical write-up in ACL paper format — methods, training dynamics, error-migration analysis, ablations, and the deployment study — is available at [paper/main.pdf](paper/main.pdf).

## Results

Model progression on the 650-sample three-tier benchmark (T1: 250 / T2: 250 / T3: 150):

| Stage | Model | Overall F1 | T2 Adversarial Recall | FPR | Format Error |
|---|---|---|---|---|---|
| Base | Qwen3-1.7B | 0.000 | – | – | 100% |
| SFT | sft-v1 | 0.862 | 0.800 | 0.71% | 0.15% |
| DPO | dpo-v2 | 0.867 | 0.812 | 3.57% | 0.15% |
| GRPO | grpo-v1 | 0.874 | 0.828 | 2.86% | 0.0% |
| Serving | guardlm-final (vLLM, bf16) | **0.8755** | 0.820 | 3.57% | **0.00%** |

Serving capacity (RTX 4090, single GPU, bf16, JSON-schema constrained decoding on):

| Concurrency | Throughput | P99 E2E Latency | TTFT P99 |
|---|---|---|---|
| 1 | 28.2 req/s | 35 ms | 27 ms |
| 4 | 49.5 req/s | 81 ms | 45 ms |
| 16 | 62.3 req/s | 266 ms | 74 ms |

Quantization trade-off (650-sample benchmark, identical protocol):

| Deployment | F1 | Recall | FPR | Weight Size | Eval Time |
|---|---|---|---|---|---|
| HF transformers (bf16) | 0.8740 | 0.7824 | 2.86% | 3.3 GiB | ~4.5 min |
| vLLM (bf16) | **0.8755** | 0.7863 | 3.57% | 3.3 GiB | 183 s |
| vLLM (AWQ 4-bit) | 0.8274 | 0.7098 | **2.14%** | **1.3 GiB** | **69 s** |

vLLM bf16 is the production form: zero accuracy loss against the training-time baseline with ~2.4x batch throughput. AWQ 4-bit costs 4.8-pt F1, concentrated in recall on adversarial homophone/split variants (homophone −18.2 pt), in exchange for 61% smaller weights and 2.6x faster batch inference; it is suitable for ≤ 8 GB VRAM deployments or offline bulk pre-screening, not as the primary serving path.

## Pipeline

```
Public datasets (COLD / CValues / Safety-Prompts)
        │
        ▼
Data engine ── clean, unify schema, LLM synthesis, adversarial augment
        │
        ▼
SFT ── classification instruction tuning (QLoRA)
        │
        ▼
DPO ── preference pairs from error attribution
        │
        ▼
GRPO ── outcome-rewarded RL on adversarial cases
        │
        ▼
Three-tier benchmark + harness reports ──► vLLM serving (bf16, constrained decoding)
```

## Repository Structure

```
data/            dataset pipeline stages (raw / interim / sft / rl / cpt / eval)
scripts/         environment setup, training, serving, benchmark, verification
training/        per-stage configs and launchers (cpt / sft / dpo / grpo)
harness/         evaluation pipeline (python -m harness.run)
demo/            FastAPI wrapper + web demo page for the vLLM backend
bench/           load-test scripts
configs/         synthesis scenario matrices
review/          human-review worksheets archive
reports/         evaluation reports per model version
paper/           ACL-style technical paper (LaTeX source + figures)
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

A sanity-check script runs QLoRA SFT on the bundled identity dataset and merges the adapter back into the base model:

```bash
# 1. QLoRA SFT — 230 steps, ~95 s on RTX 4090
bash scripts/m0-8-run-sft-v2.sh

# 2. Merge LoRA into the base model (dequantized bf16 export)
bash scripts/m0-8-merge.sh

# 3. Verify the fine-tune via inference
python scripts/m0-8-chat-verify.py
```

## Deployment

The production form is the bf16 model (`guardlm-final`) served by vLLM with JSON-schema constrained decoding, which pins the format error rate at 0.00%.

```bash
# bf16 (production)
bash scripts/m6-2-serve.sh

# AWQ 4-bit (low-VRAM option, see trade-off table above)
bash scripts/m6-2-serve.sh guardlm /root/models/guardlm-awq
```

Prefix caching is disabled by default to keep benchmark numbers reproducible.

### Demo API

```bash
uvicorn demo.app:app --host 0.0.0.0 --port 7860
```

The demo wraps the vLLM backend with constrained decoding plus layered parse fallback, and follows a fail-closed discipline: when the inference backend is unreachable or a verdict cannot be parsed, it returns an explicit 502 instead of a fabricated verdict.

## Roadmap

| Stage | Scope | Status |
|---|---|---|
| Environment & pipeline validation | CUDA + LLaMA-Factory, QLoRA SFT closed loop | Done |
| Data engine | corpus ingestion, adversarial augmentation, LLM synthesis, benchmark sets | Done |
| SFT | classification instruction tuning (sft-v1, F1 0.862) | Done |
| DPO / GRPO | preference optimization + outcome-rewarded RL (dpo-v2, grpo-v1, F1 0.874) | Done |
| CPT ablation | domain continued pre-training vs. direct SFT (sft-v2) | Done (ablation; production keeps grpo-v1) |
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
