#!/usr/bin/env bash
# M5-2: 从 TensorBoard events 文件读 loss 曲线（绕过 stdout 块缓冲问题）
/root/guardlm-venv/bin/python - <<'EOF'
import glob
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

runs_dir = "/root/saves/Qwen3-1.7B/guardlm-cpt-v1/runs"
event_files = glob.glob(runs_dir + "/**/events*", recursive=True)
if not event_files:
    print("no event files found in", runs_dir)
    raise SystemExit(1)

ea = EventAccumulator(sorted(event_files)[-1])
ea.Reload()

tags = ea.Tags()["scalars"]
print("scalar tags:", tags)

for tag in ["train/loss", "train/grad_norm", "train/learning_rate"]:
    if tag in tags:
        events = ea.Scalars(tag)
        pts = events[:: max(1, len(events) // 12)]
        print(f"\n[{tag}] {len(events)} pts")
        for e in pts:
            print(f"  step {e.step:4d}: {e.value:.4f}")
EOF
