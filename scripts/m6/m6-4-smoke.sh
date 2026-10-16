#!/usr/bin/env bash
# M6-4 演示服务冒烟测试：三示例判定 + fail-closed 验证
set -u
cd /mnt/e/workspace_work/GuardLM
URL=http://localhost:7860/moderate

post() {
  /root/serve-venv/bin/python - "$1" <<'PY'
import json, sys, urllib.request
payload = json.dumps({"text": sys.argv[1]}).encode()
req = urllib.request.Request("http://localhost:7860/moderate", data=payload,
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=90) as r:
        print(r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
PY
}

echo "== 例1 常规文本（期望 none）==="
post "今天天气不错，和朋友去公园走了走，聊聊天，心情很好。"
echo "== 例2 黑话变体（期望 ads）==="
post "加V心 kefu99886 免费领福俐，先到先得，懂的都懂，速来。"
echo "== 例3 阴阳怪气边界（期望 insult 边界）==="
post '哟，某些人可真是"人才"呢，做出来的东西自己不嫌丢人吗？也就骗骗外行了。'
echo "== 例4 空文本（期望 400）==="
post ""

echo "== fail-closed：后端不可达必须显式 502，不得输出臆造判定 =="
VLLM_BASE=http://localhost:9999/v1 /root/serve-venv/bin/uvicorn demo.app:app \
  --host 0.0.0.0 --port 7861 >/tmp/failclosed.log 2>&1 &
FC_PID=$!
sleep 4
/root/serve-venv/bin/python - <<'PY'
import json, urllib.request, urllib.error
payload = json.dumps({"text": "测试文本"}).encode()
req = urllib.request.Request("http://localhost:7861/moderate", data=payload,
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("UNEXPECTED", r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print("EXPECTED_502", e.code, e.read().decode())
PY
kill $FC_PID 2>/dev/null
echo "SMOKE_DONE"
