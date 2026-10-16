#!/usr/bin/env bash
# M5: 检查 llamafactory 在 transformers 4.56 (M4 升级后) 下是否仍可用
P=/root/guardlm-venv/bin/python
$P -m pip list 2>/dev/null | grep -Ei '^(llamafactory|llamafactory-cli|transformers|trl|peft|torch|datasets) '
echo "--- import test ---"
$P -c "import llamafactory; print('llamafactory', llamafactory.__version__, 'OK')"
