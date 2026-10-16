#!/usr/bin/env bash
# M6-4 预检：serve-venv 与其依赖
set -u
if [ -d /root/serve-venv ]; then
  echo "serve-venv EXISTS"
  /root/serve-venv/bin/python - <<'PY'
mods = ["fastapi", "uvicorn", "openai"]
for m in mods:
    try:
        mod = __import__(m)
        print(m, "OK", getattr(mod, "__version__", "?"))
    except ImportError as e:
        print(m, "MISSING", e)
PY
else
  echo "serve-venv MISSING"
fi
