#!/bin/bash
# M6-2: serve-venv 补充依赖（harness 在 serve-venv 跑 vLLM 评测所需）
set -e
/root/serve-venv/bin/pip install json_repair 2>&1 | tail -2
/root/serve-venv/bin/python -c "import json_repair, pydantic, openai; print('harness deps ok')"
