# -*- coding: utf-8 -*-
"""M2: 显存峰值测量——同配置小样本复跑 + nvidia-smi 循环采样。"""
import re
import subprocess
import threading
import time

import yaml

SRC = "/mnt/e/workspace_work/GuardLM/training/sft/sft-v1.yaml"
DST = "/tmp/memtest.yaml"

cfg = yaml.safe_load(open(SRC))
cfg.update({
    "max_samples": 512,
    "num_train_epochs": 1.0,
    "output_dir": "/tmp/memtest",
    "eval_strategy": "no",
    "save_steps": 9999,
    "val_size": 0,
})
yaml.dump(cfg, open(DST, "w"), allow_unicode=True)

peak = [0]
stop = threading.Event()


def sample():
    while not stop.is_set():
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True).stdout.strip().splitlines()
        if out:
            peak[0] = max(peak[0], int(out[0]))
        time.sleep(2)


t = threading.Thread(target=sample, daemon=True)
t.start()
t0 = time.time()
r = subprocess.run(
    ["/root/guardlm-venv/bin/llamafactory-cli", "train", DST],
    capture_output=True, text=True, cwd="/root/LLaMA-Factory")
stop.set()
dur = time.time() - t0
ok = r.returncode == 0
print(f"train ok={ok} dur={dur:.0f}s (512 samples, 1 epoch)")
print(f"GPU peak (含桌面常驻): {peak[0]} MiB")
pat = re.compile(r"'loss': [0-9.]+")
tail = pat.findall(r.stdout + r.stderr)[-3:] if ok else "N/A"
print(f"train_loss tail: {tail}")
