# -*- coding: utf-8 -*-
"""JSON 容错解析（M2 手册六层防御的前 4 层）。

层级:
  L1 剥代码块   ```json ... ``` / ``` ... ```
  L2 截取大括号  取首个 { 到配对/最后 } 的片段（前后的寒暄文本丢弃）
  L3 json.loads
  L4 json_repair 修尾逗号/引号缺失等可修复畸形
  L5 pydantic 校验  label 枚举 / risk ∈ [0,1] / extra="forbid"（多余字段拒绝）

返回 (parsed_dict | None, level)，level ∈ {"clean", "repaired", "format_error"}。
格式错误率 = format_error 数 / 总数，是 Harness 的被测指标之一（不做静默自修复）。

自测:  python -m harness.parse   注入 5 条畸形样本验证分级正确（DoD f02）。
"""
import json
import re
import sys

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal

VALID_LABELS = ("insult", "porn", "ads", "illegal", "none")


class PredSchema(BaseModel):
    """评测输出的严格 schema。extra=forbid: 基座/SFT 模型多吐一个字段即计格式错误。"""
    model_config = ConfigDict(extra="forbid")
    label: Literal["insult", "porn", "ads", "illegal", "none"]
    risk: float = Field(ge=0.0, le=1.0)
    reason: str


def _strip_codeblock(text):
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if m:
        return m.group(1).strip()
    return t


def _extract_braces(text):
    """截取首个 { 起的 JSON 片段。优先配对扫描，失败则首尾截取。"""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    end = text.rfind("}")
    return text[start:end + 1] if end > start else text[start:]


def parse_pred(text):
    """返回 (dict|None, level)。level: clean / repaired / format_error。"""
    t = _strip_codeblock(text or "")
    frag = _extract_braces(t)
    if frag is None:
        return None, "format_error"

    obj = None
    level = "clean"
    try:
        obj = json.loads(frag)
    except json.JSONDecodeError:
        try:
            import json_repair
            obj = json_repair.repair_json(frag, return_objects=True)
            level = "repaired"
        except Exception:
            return None, "format_error"

    if not isinstance(obj, dict):
        return None, "format_error"
    try:
        validated = PredSchema(**obj)
        return validated.model_dump(), level
    except ValidationError:
        return None, "format_error"


# ---------- 畸形注入自测（DoD f02: 5/5 按预期分级，不允许静默通过） ----------
SELFTEST = [
    # (名称, 注入文本, 预期 level)
    ("fence", '```json\n{"label": "none", "risk": 0.1, "reason": "ok"}\n```', "clean"),
    ("寒暄前缀", '好的，以下是判定结果：{"label": "insult", "risk": 0.9, "reason": "脏话"}',
     "clean"),
    ("尾逗号", '{"label": "none", "risk": 0.1, "reason": "ok",}', "repaired"),
    ("截断", '{"label": "insu', "format_error"),
    ("类型漂移", '{"label": "none", "risk": "低", "reason": "ok"}', "format_error"),
    ("多余字段", '{"label": "none", "risk": 0.1, "reason": "ok", "confidence": 0.9}', "format_error"),
]


def selftest():
    ok = 0
    for name, text, want in SELFTEST:
        obj, got = parse_pred(text)
        status = "PASS" if got == want else "FAIL"
        if got == want:
            ok += 1
        print(f"[{status}] {name:8s} -> {got:12s} (expect {want})  obj={'有' if obj else '无'}")
    print(f"\n{ok}/{len(SELFTEST)} 分级正确")
    sys.exit(0 if ok == len(SELFTEST) else 1)


if __name__ == "__main__":
    selftest()
