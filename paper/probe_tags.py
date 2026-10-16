#!/usr/bin/env python
"""Probe TensorBoard event files: list all scalar tags and step/value ranges."""
import glob
import sys

from tensorboard.backend.event_processing import event_accumulator

SAVES = "/root/saves/Qwen3-1.7B"
RUNS = {
    "sft-v1": f"{SAVES}/guardlm-sft-v1/runs/*/",
    "dpo-v2": f"{SAVES}/guardlm-dpo-v2/runs/*/",
    "grpo-v1": f"{SAVES}/guardlm-grpo-v1/runs/*/",
    "cpt-v1": f"{SAVES}/guardlm-cpt-v1/runs/*/",
}


def load_tags(pattern):
    dirs = sorted(glob.glob(pattern))
    if not dirs:
        return None
    d = dirs[-1]  # latest run dir
    files = sorted(glob.glob(f"{d}/events.out.tfevents.*"))
    if not files:
        return None
    ea = event_accumulator.EventAccumulator(d, size_guidance={"scalars": 0})
    ea.Reload()
    return ea


def main():
    for name, pattern in RUNS.items():
        print(f"===== {name} =====")
        try:
            ea = load_tags(pattern)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR: {e}")
            continue
        if ea is None:
            print("  no events found")
            continue
        tags = ea.Tags().get("scalars", [])
        for t in tags:
            ev = ea.Scalars(t)
            if not ev:
                continue
            steps = [x.step for x in ev]
            vals = [x.value for x in ev]
            print(f"  {t}: n={len(ev)} step=[{steps[0]}..{steps[-1]}] "
                  f"v=[{min(vals):.4g}..{max(vals):.4g}]")


if __name__ == "__main__":
    sys.exit(main())
