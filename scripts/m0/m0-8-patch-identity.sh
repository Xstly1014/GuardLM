#!/bin/bash
# M0-8: replace identity placeholders ({{name}} -> GuardLM, {{author}} -> 郭剑华)
# so the fine-tune has a concrete, observable effect on self-identification.
set -e
source /root/guardlm-venv/bin/activate
python - <<'PYEOF'
import json

path = "/root/LLaMA-Factory/data/identity.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)

for d in data:
    d["output"] = d["output"].replace("{{name}}", "GuardLM").replace("{{author}}", "郭剑华")

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("placeholders replaced, sample outputs:")
print(" ", data[0]["output"])
print(" ", data[-1]["output"])
PYEOF
echo "IDENTITY PATCH DONE"
