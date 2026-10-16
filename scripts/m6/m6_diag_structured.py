#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M6-2 快速诊断：无约束 vs 约束解码各发一条请求，区分引擎问题与 XGrammar 问题。"""
import json
import time
import urllib.request

URL = "http://localhost:8000/v1/chat/completions"
TEXT = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。\n加V心 kefu99886 免费领福俐，先到先得"

SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": ["insult", "porn", "ads", "illegal", "none"]},
        "risk": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["label", "risk", "reason"],
    "additionalProperties": False,
}


def post(body, timeout=60):
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data, time.time() - t0


base = {
    "model": "guardlm",
    "messages": [{"role": "user", "content": TEXT}],
    "max_tokens": 64,
    "temperature": 0.7,
    "top_p": 0.8,
    "chat_template_kwargs": {"enable_thinking": False},
}

print("=== 无约束 ===")
try:
    d, dt = post(dict(base), timeout=60)
    print(f"[{dt:.2f}s]", d["choices"][0]["message"]["content"][:200])
    print("finish:", d["choices"][0]["finish_reason"])
except Exception as e:
    print("FAIL:", e)

print("=== 约束解码 ON ===")
body = dict(base)
body["response_format"] = {"type": "json_schema",
                           "json_schema": {"name": "verdict", "schema": SCHEMA}}
try:
    d, dt = post(body, timeout=120)
    print(f"[{dt:.2f}s]", d["choices"][0]["message"]["content"][:200])
    print("finish:", d["choices"][0]["finish_reason"])
except Exception as e:
    print("FAIL:", e)
