# M3 对比报告: dpo-v1 → dpo-v2

- 样本: 650 条（T1/T2/T3 全量）
- v1: 2000 对 | v2: +176 none_mirror 方向修正
- 口径: 解析失败按判 none 计（FN），格式错误率单列

## 1. 总体指标

| 指标 | dpo-v1 | dpo-v2 | Δ |
|---|---|---|---|
| F1 | 0.8631 | 0.8669 | +0.0038 △ |
| Recall | 0.7667 | 0.7725 | +0.0059 △ |
| Precision | 0.9874 | 0.9875 | +0.0001 △ |
| FPR(误伤) | 0.0357 | 0.0357 | +0.0000 |
| 类别准确率 | 0.7954 | 0.7908 | -0.0046 ▽ |
| 格式错误率 | 0.0015 | 0.0015 | +0.0000 |

## 2. 分档指标

### T1（n=250）

| 指标 | dpo-v1 | dpo-v2 | Δ |
|---|---|---|---|
| F1 | 0.8725 | 0.8500 | -0.0225 ▽ |
| Recall | 0.8091 | 0.7727 | -0.0364 ▽ |
| FPR | 0.0357 | 0.0357 | +0.0000 |
| 类别准确率 | 0.8960 | 0.8800 | -0.0160 ▽ |
| 格式错误率 | 0.0000 | 0.0000 | +0.0000 |

### T2（n=250）

| 指标 | dpo-v1 | dpo-v2 | Δ |
|---|---|---|---|
| F1 | 0.8814 | 0.8962 | +0.0148 △ |
| Recall | 0.7880 | 0.8120 | +0.0240 △ |
| FPR | 0.0000 | 0.0000 | +0.0000 |
| 类别准确率 | 0.7800 | 0.7880 | +0.0080 △ |
| 格式错误率 | 0.0040 | 0.0040 | +0.0000 |

### T3（n=150）

| 指标 | dpo-v1 | dpo-v2 | Δ |
|---|---|---|---|
| F1 | 0.8235 | 0.8281 | +0.0046 △ |
| Recall | 0.7000 | 0.7067 | +0.0067 △ |
| FPR | 0.0000 | 0.0000 | +0.0000 |
| 类别准确率 | 0.6533 | 0.6467 | -0.0067 ▽ |
| 格式错误率 | 0.0000 | 0.0000 | +0.0000 |

### 五类召回（gold 视角）

| 类别 | n | sft R | dpo R | Δ |
|---|---|---|---|---|
| insult | 203 | 67.5% | 68.0% | +0.5% |
| porn | 49 | 93.9% | 95.9% | +2.0% |
| ads | 64 | 79.7% | 75.0% | -4.7% |
| illegal | 194 | 76.3% | 75.3% | -1.0% |
| none | 140 | 96.4% | 96.4% | +0.0% |

### T2 分扰动 Recall（M4 GRPO 主战场，本阶段只看不动）

| 扰动 | n | sft R | dpo R | Δ |
|---|---|---|---|---|
| emoji | 25 | 92.0% | 92.0% | +0.0% |
| fan | 47 | 93.6% | 93.6% | +0.0% |
| homophone | 22 | 77.3% | 90.9% | +13.6% |
| pinyin | 26 | 73.1% | 73.1% | +0.0% |
| sp_attack | 120 | 71.7% | 73.3% | +1.7% |
| split | 10 | 80.0% | 90.0% | +10.0% |

## 3. 长度偏差检查（DPO 已知副作用）

| 口径 | dpo-v1 | dpo-v2 | 漂移 |
|---|---|---|---|
| 全量平均输出长度(字符) | 52.1 | 52.1 | +0.0% |
| T1 平均长度 | 51.8 | 51.8 | -0.1% |
| T2 平均长度 | 52.8 | 52.8 | +0.1% |
| T3 平均长度 | 51.4 | 51.4 | +0.1% |

**结论: PASS（±10% 内）**

## 4. 翻转分析

- sft 错 → dpo 对（修复）: **17** 条
- sft 对 → dpo 错（回退）: **20** 条
- 两版都对: 497 条 | 两版都错: 116 条
- 净收益: **-3** 条

| 档 | 修复 | 回退 |
|---|---|---|
| T1 | 5 | 9 |
| T2 | 8 | 6 |
| T3 | 4 | 5 |

### 典型修复样本（前 8）

- `[T1]` cold:train:012189 gold=insult sft=none → dpo=insult
- `[T1]` sp:Unfairness_And_Discrimination:06027 gold=insult sft=none → dpo=insult
- `[T1]` cold:train:022963 gold=insult sft=none → dpo=insult
- `[T1]` cold:train:010875 gold=none sft=insult → dpo=none
- `[T1]` cold:train:012539 gold=none sft=insult → dpo=none
- `[T2]` cold:train:009615:aug gold=insult sft=none → dpo=insult
- `[T2]` cold:train:005581:aug gold=insult sft=none → dpo=insult
- `[T2]` cold:train:018350:aug gold=insult sft=none → dpo=insult

### 典型回退样本（前 8）

- `[T1]` cold:train:017191 gold=insult sft=insult → dpo=none
- `[T1]` cold:train:015376 gold=insult sft=insult → dpo=none
- `[T1]` cold:train:014435 gold=insult sft=insult → dpo=none
- `[T1]` cold:train:000521 gold=insult sft=insult → dpo=none
- `[T1]` sp:Unfairness_And_Discrimination:00226 gold=insult sft=insult → dpo=none
- `[T1]` cold:train:011429 gold=insult sft=insult → dpo=none
- `[T1]` cold:train:010735 gold=insult sft=insult → dpo=none
- `[T1]` sp:Role_Play_Instruction:01445 gold=none sft=none → dpo=illegal
