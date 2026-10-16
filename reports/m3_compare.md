# M3 对比报告: sft-v1 → dpo-v1

- 样本: 650 条（T1/T2/T3 全量）
- sft-v1: QLoRA SFT (M2 产物)  |  dpo-v1: β=0.1, lr=1e-5, 1 epoch, 2000 对
- 口径: 解析失败按判 none 计（FN），格式错误率单列

## 1. 总体指标

| 指标 | sft-v1 | dpo-v1 | Δ(dpo-sft) |
|---|---|---|---|
| F1 | 0.8619 | 0.8631 | +0.0012 △ |
| Recall | 0.7588 | 0.7667 | +0.0078 △ |
| Precision | 0.9974 | 0.9874 | -0.0100 ▽ |
| FPR(误伤) | 0.0071 | 0.0357 | -0.0286 ▽ |
| 类别准确率 | 0.7938 | 0.7954 | +0.0015 △ |
| 格式错误率 | 0.0015 | 0.0015 | +0.0000 |

## 2. 分档指标

### T1（n=250）

| 指标 | sft-v1 | dpo-v1 | Δ |
|---|---|---|---|
| F1 | 0.8731 | 0.8725 | -0.0005 ▽ |
| Recall | 0.7818 | 0.8091 | +0.0273 △ |
| FPR | 0.0071 | 0.0357 | -0.0286 ▽ |
| 类别准确率 | 0.9000 | 0.8960 | -0.0040 ▽ |
| 格式错误率 | 0.0000 | 0.0000 | +0.0000 |

### T2（n=250）

| 指标 | sft-v1 | dpo-v1 | Δ |
|---|---|---|---|
| F1 | 0.8889 | 0.8814 | -0.0075 ▽ |
| Recall | 0.8000 | 0.7880 | -0.0120 ▽ |
| FPR | 0.0000 | 0.0000 | +0.0000 |
| 类别准确率 | 0.7880 | 0.7800 | -0.0080 ▽ |
| 格式错误率 | 0.0040 | 0.0040 | +0.0000 |

### T3（n=150）

| 指标 | sft-v1 | dpo-v1 | Δ |
|---|---|---|---|
| F1 | 0.8048 | 0.8235 | +0.0187 △ |
| Recall | 0.6733 | 0.7000 | +0.0267 △ |
| FPR | 0.0000 | 0.0000 | +0.0000 |
| 类别准确率 | 0.6267 | 0.6533 | +0.0267 △ |
| 格式错误率 | 0.0000 | 0.0000 | +0.0000 |

### 五类召回（gold 视角）

| 类别 | n | sft R | dpo R | Δ |
|---|---|---|---|---|
| insult | 203 | 67.0% | 67.5% | +0.5% |
| porn | 49 | 91.8% | 93.9% | +2.0% |
| ads | 64 | 76.6% | 79.7% | +3.1% |
| illegal | 194 | 75.8% | 76.3% | +0.5% |
| none | 140 | 99.3% | 96.4% | -2.9% |

### T2 分扰动 Recall（M4 GRPO 主战场，本阶段只看不动）

| 扰动 | n | sft R | dpo R | Δ |
|---|---|---|---|---|
| emoji | 25 | 96.0% | 92.0% | -4.0% |
| fan | 47 | 93.6% | 93.6% | +0.0% |
| homophone | 22 | 90.9% | 77.3% | -13.6% |
| pinyin | 26 | 69.2% | 73.1% | +3.8% |
| sp_attack | 120 | 71.7% | 71.7% | +0.0% |
| split | 10 | 80.0% | 80.0% | +0.0% |

## 3. 长度偏差检查（DPO 已知副作用）

| 口径 | sft-v1 | dpo-v1 | 漂移 |
|---|---|---|---|
| 全量平均输出长度(字符) | 52.1 | 52.1 | -0.0% |
| T1 平均长度 | 51.8 | 51.8 | +0.1% |
| T2 平均长度 | 52.8 | 52.8 | -0.1% |
| T3 平均长度 | 51.5 | 51.4 | -0.2% |

**结论: PASS（±10% 内）**

## 4. 翻转分析

- sft 错 → dpo 对（修复）: **17** 条
- sft 对 → dpo 错（回退）: **16** 条
- 两版都对: 500 条 | 两版都错: 117 条
- 净收益: **+1** 条

| 档 | 修复 | 回退 |
|---|---|---|
| T1 | 7 | 8 |
| T2 | 5 | 7 |
| T3 | 5 | 1 |

### 典型修复样本（前 8）

- `[T1]` cold:dev:003060 gold=insult sft=none → dpo=insult
- `[T1]` cold:train:017191 gold=insult sft=none → dpo=insult
- `[T1]` cold:train:015376 gold=insult sft=none → dpo=insult
- `[T1]` cold:train:000521 gold=insult sft=none → dpo=insult
- `[T1]` sp:Unfairness_And_Discrimination:00226 gold=insult sft=none → dpo=insult
- `[T1]` cold:train:004583 gold=insult sft=none → dpo=insult
- `[T1]` cold:train:010735 gold=insult sft=none → dpo=insult
- `[T2]` cold:train:010280:aug gold=insult sft=none → dpo=insult

### 典型回退样本（前 8）

- `[T1]` cold:train:012189 gold=insult sft=insult → dpo=none
- `[T1]` cold:dev:001019 gold=insult sft=insult → dpo=none
- `[T1]` sp:Unfairness_And_Discrimination:06027 gold=insult sft=insult → dpo=none
- `[T1]` cold:dev:002992 gold=insult sft=insult → dpo=none
- `[T1]` cold:dev:003140 gold=none sft=none → dpo=insult
- `[T1]` cold:train:009268 gold=none sft=none → dpo=insult
- `[T1]` cold:train:010875 gold=none sft=none → dpo=insult
- `[T1]` cold:train:012539 gold=none sft=none → dpo=insult
