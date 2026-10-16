# -*- coding: utf-8 -*-
"""M4-1: GuardLM GRPO 四奖励函数（TRL 统一签名）。

设计原则（M4 手册任务1 四黄金法则）:
  ① 组合多个函数各司一职——任何单维奖励都会被钻空子（v8 空conclusion 案例）
  ② 权重分级——正确性 2.0 > 格式 1.0 > 长度 0.1~0.5（核心任务信号必须压倒格式）
  ③ 增量奖励（partial credit）——阶梯给分让梯度有层次，全有全无 = 稀疏信号
  ④ 独立测试——test_rewards.py 逐个单测 + 离线 sanity

权重表:
  format_reward        纯JSON一次过 1.0 / 清洗过 0.75 / repair过 0.5 / 失败 0     (×1.0)
  correctness_reward   label对 2.0 + risk误差<0.2 加 0.5 / 错 0                    (×2.0)
  robust_reward        aug样本且正确 → correctness × 0.5 叠加（等效×1.5系数）      (×1.0)
  length_penalty       超长阶梯扣分 + 空reason扣0.2                                (×1.0, 负值)

TRL 签名约定:
  def r(prompts, completions, answer=None, **kwargs) -> list[float]
  - completions 嵌套结构: comp[0]['content'] 才是纯文本（conversational 格式）
  - answer/aug 列由数据集额外携带，TRL 自动透传进函数
"""
import json
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, BASE)

# 字符→token 近似（未注入 tokenizer 时使用）: JSON+中文 reason ≈ 1.6 字符/token
CHARS_PER_TOKEN = 1.6
LEN_LIMIT_CHARS = int(80 * CHARS_PER_TOKEN)  # 手册 max_completion_length=80 token
REASON_EMPTY_PENALTY = 0.2

_TOKENIZER = None


def set_tokenizer(tok):
    """训练脚本注入 tokenizer，使长度惩罚精确按 token 计。"""
    global _TOKENIZER
    _TOKENIZER = tok


def _token_len(text):
    if _TOKENIZER is not None:
        return len(_TOKENIZER(text)["input_ids"])
    return len(text) / CHARS_PER_TOKEN


def _content(comp):
    """TRL completions 嵌套结构提取: [{role, content}] 或纯文本。"""
    if isinstance(comp, list) and comp and isinstance(comp[0], dict):
        return comp[0].get("content", "")
    return comp if isinstance(comp, str) else ""


def _parse_json(text):
    """三层解析，返回 (dict|None, level)。level: 3=直接过 2=清洗过 1=repair过 0=失败。"""
    t = (text or "").strip()
    if not t:
        return None, 0
    try:  # L3 直接过
        return json.loads(t), 3
    except (json.JSONDecodeError, ValueError):
        pass
    # L2 清洗: 剥代码块 / 截大括号
    if "```" in t:
        for seg in t.split("```"):
            seg = seg.strip()
            if seg.startswith("json"):
                seg = seg[4:].strip()
            if seg.startswith("{"):
                t = seg
                break
    if t.count("{") >= 1 and t.count("}") >= 1:
        s, e = t.find("{"), t.rfind("}")
        t = t[s:e + 1]
    try:
        return json.loads(t), 2
    except (json.JSONDecodeError, ValueError):
        pass
    try:  # L1 repair
        import json_repair
        obj = json_repair.repair_json(t, return_objects=True)
        if isinstance(obj, dict) and "label" in obj:
            return obj, 1
    except Exception:
        pass
    return None, 0


def format_reward(prompts, completions, **kwargs):
    """① 格式奖励: 巩固 M2 格式成果，防退化。"""
    out = []
    for comp in completions:
        _, lvl = _parse_json(_content(comp))
        out.append({3: 1.0, 2: 0.75, 1: 0.5}.get(lvl, 0.0))
    return out


def _maybe_json(x):
    """TRL 透传的列值可能是 json 序列化字符串（Dataset 列限制），统一反序列化。"""
    if isinstance(x, str):
        try:
            return json.loads(x)
        except (json.JSONDecodeError, ValueError):
            return None
    return x


def correctness_reward(prompts, completions, answer=None, **kwargs):
    """② 正确性奖励: 核心任务信号，权重压倒格式。"""
    out = []
    for i, comp in enumerate(completions):
        ans = answer[i] if answer and i < len(answer) else None
        ans = _maybe_json(ans)
        if not ans:
            out.append(0.0)
            continue
        obj, _ = _parse_json(_content(comp))
        if obj is None or obj.get("label") != ans.get("label"):
            out.append(0.0)
            continue
        score = 2.0
        try:
            if abs(float(obj.get("risk", -1)) - float(ans.get("risk", -2))) < 0.2:
                score += 0.5
        except (TypeError, ValueError):
            pass
        out.append(score)
    return out


def robust_reward(prompts, completions, answer=None, aug=None, **kwargs):
    """③ 对抗鲁棒奖励: aug 样本仍正确 → correctness × 0.5 叠加（等效×1.5）。"""
    base = correctness_reward(prompts, completions, answer=answer)
    out = []
    for i, comp in enumerate(completions):
        is_aug = bool(aug and i < len(aug) and aug[i])
        out.append(base[i] * 0.5 if is_aug else 0.0)
    return out


def length_penalty(prompts, completions, **kwargs):
    """④ 长度惩罚: 防输出膨胀与空 reason 刷分（负值）。"""
    out = []
    for comp in completions:
        text = _content(comp)
        n = _token_len(text)
        pen = 0.0
        if n > 80:
            pen -= 0.1 * int((n - 80) // 20)  # 每超 20 token 扣 0.1
        obj, _ = _parse_json(text)
        if obj is not None and not str(obj.get("reason", "")).strip():
            pen -= REASON_EMPTY_PENALTY
        out.append(pen)
    return out


REWARD_FUNCS = [format_reward, correctness_reward, robust_reward, length_penalty]
# 权重分级已内含在函数返回值里（正确性 2.0+ > 格式 1.0 > 长度惩罚负值），
# GRPOTrainer 对 reward_funcs 直接求和，不叠加外部权重——避免双重加权。
REWARD_WEIGHTS = {fn.__name__: 1.0 for fn in REWARD_FUNCS}


def total_reward(completions, answer, aug=None):
    """离线总分（单测/sanity 用），与 GRPOTrainer 求和方式一致。"""
    prompts = [None] * len(completions)
    comps = [c if isinstance(c, str) else [{"role": "assistant", "content": c}]
             for c in completions]
    total = [0.0] * len(comps)
    for fn in REWARD_FUNCS:
        scores = fn(prompts, comps, answer=answer, aug=aug)
        for i in range(len(total)):
            total[i] += scores[i]
    return total
