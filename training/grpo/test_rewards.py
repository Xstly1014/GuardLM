# -*- coding: utf-8 -*-
"""M4-1: 奖励函数单测 + 离线 sanity。

单测（黄金法则④）: 构造正/反/边界样例逐函数喂分，断言符合设计表。
离线 sanity: dpo-v2 在 T2 上的真实输出喂分 → 正确样本均分应明显高于错误样本
              （信号可分性：>4.0 正确 / <1.0 错误 / 分布无异常聚集）。

用法:
  python training/grpo/test_rewards.py                  # 单测
  python training/grpo/test_rewards.py --sanity \
      --pred reports/artifacts/dpo-v2.pred.jsonl --tier T2        # 离线 sanity
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rewards import (format_reward, correctness_reward, robust_reward,
                     length_penalty, total_reward, _parse_json)

OK_JSON = '{"label": "insult", "risk": 0.9, "reason": "侮辱攻击性内容"}'
OK_JSON_RISK_OFF = '{"label": "insult", "risk": 0.5, "reason": "侮辱攻击性内容"}'
DIRTY_JSON = '```json\n{"label": "insult", "risk": 0.9, "reason": "x"}\n```'
BROKEN_JSON = '{"label": "insult", "risk": 0.9, "reason": '
WRONG_LABEL = '{"label": "ads", "risk": 0.9, "reason": "广告"}'
EMPTY_REASON = '{"label": "insult", "risk": 0.9, "reason": ""}'
LONG_REASON = ('{"label": "insult", "risk": 0.9, "reason": "' + "非常长的原因" * 40 + '"}')
ANS = {"label": "insult", "risk": 0.9}


def _comps(*texts):
    return [[{"role": "assistant", "content": t}] for t in texts]


def unit_tests():
    failed = []
    results = []

    def check(name, got, want):
        ok = abs(got - want) < 1e-6
        results.append((name, got, want, ok))
        if not ok:
            failed.append(name)

    # ---- ① format_reward ----
    check("fmt 纯JSON", format_reward(None, _comps(OK_JSON))[0], 1.0)
    check("fmt 清洗(代码块)", format_reward(None, _comps(DIRTY_JSON))[0], 0.75)
    lvl = _parse_json(BROKEN_JSON)[1]
    check("fmt repair碎JSON", format_reward(None, _comps(BROKEN_JSON))[0],
          {1: 0.5, 2: 0.75, 3: 1.0}.get(lvl, 0.0))
    check("fmt 完全失败", format_reward(None, _comps("垃圾输出"))[0], 0.0)
    check("fmt 嵌套提取(纯文本)", format_reward(None, [OK_JSON])[0], 1.0)

    # ---- ② correctness_reward ----
    ans = [ANS] * 6
    c = correctness_reward(None, _comps(OK_JSON, OK_JSON_RISK_OFF, WRONG_LABEL,
                                       DIRTY_JSON, BROKEN_JSON, "不是JSON"), answer=ans)
    check("corr label+risk全对", c[0], 2.5)
    check("corr label对risk差>0.2", c[1], 2.0)
    check("corr label错", c[2], 0.0)
    check("corr 清洗后label对", c[3], 2.5)
    check("corr 无answer", correctness_reward(None, _comps(OK_JSON))[0], 0.0)
    # TRL 透传 answer 为 json 序列化字符串（Dataset 列限制）——反序列化路径
    check("corr answer为json串", correctness_reward(
        None, _comps(OK_JSON), answer=[json.dumps(ANS)])[0], 2.5)
    check("robust answer为json串", robust_reward(
        None, _comps(OK_JSON), answer=[json.dumps(ANS)], aug=[True])[0], 1.25)

    # ---- ③ robust_reward ----
    aug = [True, True, False]
    r = robust_reward(None, _comps(OK_JSON, WRONG_LABEL, OK_JSON),
                      answer=[ANS, ANS, ANS], aug=aug)
    check("robust aug+正确 叠加50%", r[0], 1.25)  # (2.5)*0.5
    check("robust aug+错误=0", r[1], 0.0)
    check("robust 非aug=0", r[2], 0.0)

    # ---- ④ length_penalty ----
    p = length_penalty(None, _comps(OK_JSON, EMPTY_REASON, LONG_REASON))
    check("len 正常输出=0", p[0], 0.0)
    check("len 空reason扣0.2", p[1], -0.2)
    check("len 超长扣分<0", p[2] < 0 and p[2] <= -0.1, True)

    # ---- total ----
    t = total_reward([OK_JSON, WRONG_LABEL], [ANS, ANS], [True, False])
    check("total aug正确", t[0], 1.0 + 2.5 + 1.25 + 0.0)
    check("total 非aug错误(label错但格式完美)", t[1], 1.0)  # 只得格式分——组合奖励各司一职

    print(f"单测: {len(results) - len(failed)}/{len(results)} 通过")
    for name, got, want, ok in results:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}: got={got} want={want}")
    return not failed


def sanity(pred_path, tier):
    """离线 sanity: 真实推理输出喂分，验证信号可分性。"""
    rows = [json.loads(l) for l in open(pred_path, encoding="utf-8") if l.strip()]
    if tier:
        rows = [r for r in rows if r["tier"] == tier]
    correct, wrong = [], []
    for r in rows:
        ans = {"label": r["gold_label"], "risk": 0.9}
        aug = bool(r.get("perturb"))
        t = total_reward([r["raw"]], [ans], [aug])[0]
        (correct if r["pred_label"] == r["gold_label"] else wrong).append(t)

    mc = sum(correct) / max(len(correct), 1)
    mw = sum(wrong) / max(len(wrong), 1)
    print(f"\n[sanity] {pred_path} tier={tier} n={len(rows)}")
    print(f"  正确样本(n={len(correct)}) 均分: {mc:.3f}")
    print(f"  错误样本(n={len(wrong)}) 均分: {mw:.3f}")
    print(f"  可分性: {'PASS' if mc > mw + 1.0 else 'FAIL'} (gap={mc - mw:.3f})")
    # 分布聚集检查
    import collections
    hist = collections.Counter(round(t, 1) for t in correct + wrong)
    top = hist.most_common(1)[0]
    print(f"  分布检查: 最高聚集 {top[0]} 占 {top[1]/len(rows):.0%}"
          f" {'(PASS)' if top[1] / len(rows) < 0.6 else '(WARN 全聚集=函数bug)'}")
    return mc > mw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sanity", action="store_true")
    ap.add_argument("--pred", default="reports/artifacts/dpo-v2.pred.jsonl")
    ap.add_argument("--tier", default="T2")
    args = ap.parse_args()

    ok = unit_tests()
    if args.sanity:
        ok = sanity(args.pred, args.tier) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
