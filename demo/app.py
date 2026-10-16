# -*- coding: utf-8 -*-
"""GuardLM 演示服务（M6-4）：FastAPI + vLLM 后端。

POST /moderate: {"text": "..."} -> {"label", "risk", "reason"}
- 服务端约束解码（response_format，schema 由 PredSchema 单一契约源生成）
- M2 前四层容错（parse_pred）作双保险
- fail-closed：vLLM 不可达 / 解析失败 -> 显式错误，绝不给假结果

用法 (WSL serve-venv):
  /root/serve-venv/bin/uvicorn demo.app:app --host 0.0.0.0 --port 7860
"""
import os
import sys
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from harness.backend import verdict_response_format  # noqa: E402
from harness.parse import parse_pred  # noqa: E402

VLLM_BASE = os.environ.get("VLLM_BASE", "http://localhost:8000/v1")
MODEL = os.environ.get("GUARDLM_MODEL", "guardlm")
INSTRUCTION = "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。"

app = FastAPI(title="GuardLM Demo")


class ModerateReq(BaseModel):
    text: str


@app.post("/moderate")
def moderate(req: ModerateReq):
    text = (req.text or "").strip()
    if not text:
        return JSONResponse(status_code=400, content={"error": "text 不能为空"})

    from openai import OpenAI
    client = OpenAI(base_url=VLLM_BASE, api_key="EMPTY", timeout=60.0)
    t0 = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": f"{INSTRUCTION}\n{text}"}],
            max_tokens=64, temperature=0.7, top_p=0.8,
            extra_body={
                "top_k": 20,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            response_format=verdict_response_format(),
        )
        raw = resp.choices[0].message.content or ""
    except Exception as e:  # noqa: BLE001
        # fail-closed: 后端不可达时宁可报错，不输出臆造判定
        return JSONResponse(status_code=502,
                            content={"error": f"推理服务不可用: {type(e).__name__}"})
    latency_ms = (time.perf_counter() - t0) * 1000

    obj, level = parse_pred(raw)
    if obj is None:
        # 约束解码 + 四层容错下不应走到这里；防御性 fail-closed
        return JSONResponse(status_code=502,
                            content={"error": "判定输出解析失败", "raw": raw[:200]})

    return {
        "label": obj["label"],
        "risk": obj["risk"],
        "reason": obj["reason"],
        "latency_ms": round(latency_ms, 1),
    }


_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")
