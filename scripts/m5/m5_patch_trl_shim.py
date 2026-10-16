# -*- coding: utf-8 -*-
"""M5-2: 给 trl 0.21 打兼容 shim，让 llamafactory 0.9.3 的 PPO import 链存活。

背景: M4 GRPO 需要把 trl 升级到 0.21.0（移除了 trl.core.PPODecorators /
      logprobs_from_logits），而 llamafactory 0.9.3 的 ppo/trainer.py 模块级
      import 这些符号。CPT (stage:pt) 不走 PPO，但 import 链是模块级的。

方案: 往 trl/core.py 尾部追加旧 API 的最小实现（幂等，先查符号已存在与否）。
      只影响 PPO 路径，SFT/CPT/GRPO(TRL 原生) 均不受影响。
用法: wsl /root/guardlm-venv/bin/python /mnt/e/workspace_work/GuardLM/scripts/m5_patch_trl_shim.py
"""
import importlib
import inspect
import sys

CORE = importlib.import_module("trl.core")

# 1) 逐个验证 llamafactory ppo/trainer.py 顶层 import 的符号
needed = ["PPODecorators", "logprobs_from_logits"]
missing = [n for n in needed if not hasattr(CORE, n)]
print(f"[trl.core] missing symbols: {missing}")

# 2) trl.models.utils.unwrap_model_for_generation
try:
    from trl.models.utils import unwrap_model_for_generation  # noqa: F401
    print("[trl.models.utils] unwrap_model_for_generation: OK")
except ImportError as e:
    print(f"[trl.models.utils] FAIL: {e}")
    sys.exit(1)

# 3) trl 顶层 PPOConfig / PPOTrainer
try:
    from trl import PPOConfig, PPOTrainer  # noqa: F401
    print("[trl] PPOConfig/PPOTrainer: OK")
except ImportError as e:
    print(f"[trl] PPOConfig/PPOTrainer FAIL: {e}")
    sys.exit(1)

if not missing:
    print("shim already present, nothing to do")
    sys.exit(0)

# 4) 追加 shim（旧版 trl.core 的最小等价实现）
SHIM = '''

# ---- llamafactory 0.9.3 compat shim (added by GuardLM M5) ----
from functools import wraps as _wraps


class PPODecorators(object):
    """Minimal port of legacy trl PPODecorators (only empty_device_cache is used)."""

    @classmethod
    def empty_device_cache(cls):
        def decorator(func):
            @_wraps(func)
            def wrapper(*args, **kwargs):
                import torch

                torch.cuda.empty_cache()
                return func(*args, **kwargs)

            return wrapper

        return decorator


def logprobs_from_logits(logits, labels):
    import torch
    import torch.nn.functional as F

    logp = F.log_softmax(logits.float(), dim=-1)
    logp_labels = torch.gather(logp, 2, labels.unsqueeze(2).long()).squeeze(-1)
    return logp_labels
'''

core_path = inspect.getfile(CORE)
with open(core_path, "a", encoding="utf-8") as f:
    f.write(SHIM)
print(f"shim appended to {core_path}")

# 5) 复验: 重新 import 模拟干净进程
import subprocess

r = subprocess.run(
    [sys.executable, "-c", "from trl.core import PPODecorators, logprobs_from_logits; print('reimport OK')"],
    capture_output=True, text=True,
)
print(r.stdout.strip() or r.stderr.strip())
sys.exit(r.returncode)
