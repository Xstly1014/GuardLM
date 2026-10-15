#!/usr/bin/env bash
tail -5 /root/pip_trl_upgrade.log
/root/guardlm-venv/bin/python - <<'EOF'
import trl
print("trl", trl.__version__)
from trl import GRPOTrainer
print("GRPOTrainer OK")
import transformers
print("transformers", transformers.__version__)
EOF
