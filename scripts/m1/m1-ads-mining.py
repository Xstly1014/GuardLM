# -*- coding: utf-8 -*-
"""
M1-T1 判例补丁: 从 COLD none 池挖掘广告导流（ads）样本。

背景: 公开三源没有直接的 ads 类。COLD（微博/知乎评论）里的导流广告
（"加微信""低价刷单"）原标注是无害/侮辱——按 GuardLM 判例"导流优先 ads"重标。

强特征词表（宁缺毋滥，避免把正常聊天误判为广告）:
  直接导流动作 + 变体 + 兼职灰产黑话

用法: python scripts/m1-ads-mining.py  (原地重写 data/interim/cold.unified.jsonl)
"""
import json
import os
import re

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
IN_PATH = os.path.join(BASE, "data", "interim", "cold.unified.jsonl")

ADS_STRONG = re.compile(
    r"加(微信|v|v信|vx|VX|薇|威信)|v信|vx|VX|微[信信]|薇信|威信号|"
    r"私[信聊]我|加我|捎我|\+我|扫码|二维码|点击.{0,4}链接|戳链接|"
    r"免费领|领红包|刷单|收徒|招代理|一手货源|厂家直销|"
    r"兼职.{0,8}(赚钱|日结|高薪|打字员)|高薪日结|日赚|躺赚|"
    r"低价(出|转让|货源)|折扣(价|群)|优惠券群|羊毛群"
)

def main():
    recs = []
    with open(IN_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))

    reclassified = 0
    for r in recs:
        out = json.loads(r["output"])
        if out["label"] != "none":
            continue
        if ADS_STRONG.search(r["input"]):
            out["label"] = "ads"
            out["risk"] = 0.85
            out["reason"] = "广告导流内容"
            r["output"] = json.dumps(out, ensure_ascii=False)
            r["origin_label"] = r["origin_label"] + ";ads-mined"
            reclassified += 1

    with open(IN_PATH, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[ads-mining] reclassified {reclassified} none -> ads in cold pool")
    from collections import Counter
    c = Counter(json.loads(r["output"])["label"] for r in recs)
    print("cold pool now:", dict(c))


if __name__ == "__main__":
    main()
