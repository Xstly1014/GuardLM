"""Extract real training metrics from LLaMA-Factory output for reporting/diagrams.

Usage (WSL venv): python m0-extract-metrics.py <save_dir>
Prints: summary numbers + compact loss series (for charting).
"""
import json
import sys
from pathlib import Path

save_dir = Path(sys.argv[1])

# 1) trainer_log.jsonl -> loss series
log_path = save_dir / "trainer_log.jsonl"
series = []
for line in log_path.read_text().splitlines():
    rec = json.loads(line)
    if "loss" in rec:
        series.append((rec.get("current_steps"), rec["loss"]))

# 2) train_results.json -> final numbers
res = json.loads((save_dir / "train_results.json").read_text())

# 3) trainer_state.json -> train_runtime / throughput
state = json.loads((save_dir / "trainer_state.json").read_text())

print("== train_results.json ==")
for k, v in res.items():
    print(f"{k}: {v}")
print("== trainer_state key fields ==")
for k in ("global_step", "epoch", "max_steps", "train_loss"):
    if k in state:
        print(f"{k}: {state[k]}")
print("== loss series (step,loss) ==")
print(series)
