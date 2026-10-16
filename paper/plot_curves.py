#!/usr/bin/env python
"""Generate publication-quality training figures from TensorBoard event logs."""
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tensorboard.backend.event_processing import event_accumulator

SAVES = "/root/saves/Qwen3-1.7B"
OUT = "/mnt/e/workspace_work/GuardLM/paper/figures"
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.size": 8.5,
    "axes.titlesize": 9.5,
    "axes.labelsize": 8.5,
    "legend.fontsize": 7.2,
    "xtick.labelsize": 7.8,
    "ytick.labelsize": 7.8,
    "axes.linewidth": 0.6,
    "lines.linewidth": 1.3,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
    "legend.framealpha": 0.9,
    "legend.edgecolor": "#d1d5db",
})

C = {"blue": "#2563eb", "red": "#dc2626", "green": "#059669",
     "orange": "#d97706", "gray": "#6b7280", "violet": "#7c3aed"}


def ea_for(pattern):
    d = sorted(glob.glob(pattern))[-1]
    ea = event_accumulator.EventAccumulator(d, size_guidance={"scalars": 0})
    ea.Reload()
    return ea


def xy(ea, tag):
    ev = ea.Scalars(tag)
    return [e.step for e in ev], [e.value for e in ev]


# ---------------------------------------------------------------- Figure 1
# Alignment-stage training curves: SFT / DPO / GRPO
def fig_alignment():
    sft = ea_for(f"{SAVES}/guardlm-sft-v1/runs/*/")
    dpo = ea_for(f"{SAVES}/guardlm-dpo-v2/runs/*/")
    grpo = ea_for(f"{SAVES}/guardlm-grpo-v1/runs/*/")

    fig, axes = plt.subplots(1, 3, figsize=(6.8, 1.85))

    # (a) SFT loss
    ax = axes[0]
    x, y = xy(sft, "train/loss")
    ax.plot(x, y, color=C["blue"], label="train loss")
    x, y = xy(sft, "eval/loss")
    ax.plot(x, y, "o", ms=3, color=C["red"], label="eval loss")
    ax.set_yscale("log")
    ax.set_xlabel("step")
    ax.set_ylabel("loss (log)")
    ax.set_title("(a) SFT")
    ax.legend(loc="lower left", handlelength=1.4)
    ax.annotate("eval 0.0056", xy=(1083, 0.0056), xytext=(420, 0.02),
                fontsize=7, color=C["red"],
                arrowprops=dict(arrowstyle="-", color=C["red"], lw=0.6))

    # (b) DPO loss + margins
    ax = axes[1]
    x, y = xy(dpo, "train/loss")
    ax.plot(x, y, color=C["blue"], label="DPO loss")
    ax.axhline(0.693, color=C["gray"], ls="--", lw=0.8)
    ax.text(6, 0.697, "ln 2", fontsize=7, color=C["gray"])
    ax.set_xlabel("step")
    ax.set_ylabel("loss")
    ax.set_ylim(0.52, 0.72)
    ax.set_title("(b) DPO")
    axr = ax.twinx()
    x, y = xy(dpo, "train/rewards/margins")
    axr.plot(x, y, color=C["orange"], label="margins")
    axr.set_ylabel("reward margins", color=C["orange"])
    axr.tick_params(axis="y", labelcolor=C["orange"])
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = axr.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left", handlelength=1.4)

    # (c) GRPO reward + effective-group fraction
    ax = axes[2]
    x, y = xy(grpo, "train/reward")
    ax.plot(x, y, color=C["blue"], label="mean reward")
    ax.set_xlabel("step")
    ax.set_ylabel("mean reward")
    ax.set_ylim(2.2, 4.3)
    ax.set_title("(c) GRPO")
    axr = ax.twinx()
    x, y = xy(grpo, "train/frac_reward_zero_std")
    axr.plot(x, y, color=C["gray"], label="zero-adv. groups")
    axr.set_ylabel("zero-advantage group frac.", color=C["gray"])
    axr.tick_params(axis="y", labelcolor=C["gray"])
    axr.set_ylim(0, 1.05)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = axr.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="center right", handlelength=1.4)

    fig.tight_layout(w_pad=1.6)
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}/alignment_curves.{ext}")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 2
# GRPO training health: reward components / KL & entropy / completion length
def fig_grpo_health():
    grpo = ea_for(f"{SAVES}/guardlm-grpo-v1/runs/*/")

    fig, axes = plt.subplots(1, 3, figsize=(6.8, 1.85))

    # (a) reward components
    ax = axes[0]
    for tag, label, color in (
        ("train/reward", "total", C["blue"]),
        ("train/rewards/correctness_reward/mean", "correctness", C["green"]),
        ("train/rewards/robust_reward/mean", "adversarial", C["red"]),
        ("train/rewards/format_reward/mean", "format", C["gray"]),
    ):
        x, y = xy(grpo, tag)
        ax.plot(x, y, color=color, label=label)
    ax.set_xlabel("step")
    ax.set_ylabel("reward")
    ax.set_title("(a) Reward components")
    ax.legend(loc="lower right", handlelength=1.4)

    # (b) KL + entropy (log y)
    ax = axes[1]
    x, y = xy(grpo, "train/kl")
    ax.plot(x, y, color=C["violet"], label="KL(pi || pi_ref)")
    x, y = xy(grpo, "train/entropy")
    ax.plot(x, y, color=C["orange"], label="entropy")
    ax.set_yscale("log")
    ax.set_xlabel("step")
    ax.set_ylabel("KL / entropy (log)")
    ax.set_title("(b) Policy regularizers")
    ax.legend(loc="lower right", handlelength=1.4)

    # (c) completion length stability
    ax = axes[2]
    x, y = xy(grpo, "train/completions/mean_length")
    ax.plot(x, y, color=C["blue"], label="mean length")
    x, y = xy(grpo, "train/completions/max_length")
    ax.plot(x, y, color=C["gray"], ls="--", lw=0.9, label="max length")
    ax.set_xlabel("step")
    ax.set_ylabel("completion tokens")
    ax.set_ylim(20, 55)
    ax.set_title("(c) Completion length")
    ax.legend(loc="lower right", handlelength=1.4)

    fig.tight_layout(w_pad=1.6)
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}/grpo_health.{ext}")
    plt.close(fig)


if __name__ == "__main__":
    fig_alignment()
    fig_grpo_health()
    for f in sorted(os.listdir(OUT)):
        print(f, os.path.getsize(f"{OUT}/{f}"))
    print("DONE")
