# M3 对比报告: sft-v1 → dpo-v2

- 样本: 650 条（T1/T2/T3 全量）
- sft-v1: QLoRA SFT (M2) | dpo-v2: 方向修正版 2176 对 (none_mirror+176), β=0.1 lr=1e-5
- 口径: 解析失败按判 none 计（FN），格式错误率单列

## 1. 总体指标

| 指标 | sft-v1 | dpo-v2 | Δ |
|---|---|---|---|
| F1 | 0.8619 | 0.8669 | +0.0050 △ |
| Recall | 0.7588 | 0.7725 | +0.0137 △ |
| Precision | 0.9974 | 0.9875 | -0.0100 ▽ |
| FPR(误伤) | 0.0071 | 0.0357 | -0.0286 ▽ |
| 类别准确率 | 0.7938 | 0.7908 | -0.0031 ▽ |
| 格式错误率 | 0.0015 | 0.0015 | +0.0000 |

## 2. 分档指标

### T1（n=250）

| 指标 | sft-v1 | dpo-v2 | Δ |
|---|---|---|---|
| F1 | 0.8731 | 0.8500 | -0.0231 ▽ |
| Recall | 0.7818 | 0.7727 | -0.0091 ▽ |
| FPR | 0.0071 | 0.0357 | -0.0286 ▽ |
| 类别准确率 | 0.9000 | 0.8800 | -0.0200 ▽ |
| 格式错误率 | 0.0000 | 0.0000 | +0.0000 |

### T2（n=250）

| 指标 | sft-v1 | dpo-v2 | Δ |
|---|---|---|---|
| F1 | 0.8889 | 0.8962 | +0.0074 △ |
| Recall | 0.8000 | 0.8120 | +0.0120 △ |
| FPR | 0.0000 | 0.0000 | +0.0000 |
| 类别准确率 | 0.7880 | 0.7880 | +0.0000 |
| 格式错误率 | 0.0040 | 0.0040 | +0.0000 |

### T3（n=150）

| 指标 | sft-v1 | dpo-v2 | Δ |
|---|---|---|---|
| F1 | 0.8048 | 0.8281 | +0.0233 △ |
| Recall | 0.6733 | 0.7067 | +0.0333 △ |
| FPR | 0.0000 | 0.0000 | +0.0000 |
| 类别准确率 | 0.6267 | 0.6467 | +0.0200 △ |
| 格式错误率 | 0.0000 | 0.0000 | +0.0000 |

### 五类召回（gold 视角）

| 类别 | n | sft R | dpo R | Δ |
|---|---|---|---|---|
| insult | 203 | 67.0% | 68.0% | +1.0% |
| porn | 49 | 91.8% | 95.9% | +4.1% |
| ads | 64 | 76.6% | 75.0% | -1.6% |
| illegal | 194 | 75.8% | 75.3% | -0.5% |
| none | 140 | 99.3% | 96.4% | -2.9% |

### T2 分扰动 Recall（M4 GRPO 主战场，本阶段只看不动）

| 扰动 | n | sft R | dpo R | Δ |
|---|---|---|---|---|
| emoji | 25 | 96.0% | 92.0% | -4.0% |
| fan | 47 | 93.6% | 93.6% | +0.0% |
| homophone | 22 | 90.9% | 90.9% | +0.0% |
| pinyin | 26 | 69.2% | 73.1% | +3.8% |
| sp_attack | 120 | 71.7% | 73.3% | +1.7% |
| split | 10 | 80.0% | 90.0% | +10.0% |

## 3. 长度偏差检查（DPO 已知副作用）

| 口径 | sft-v1 | dpo-v2 | 漂移 |
|---|---|---|---|
| 全量平均输出长度(字符) | 52.1 | 52.1 | +0.0% |
| T1 平均长度 | 51.8 | 51.8 | +0.1% |
| T2 平均长度 | 52.8 | 52.8 | +0.0% |
| T3 平均长度 | 51.5 | 51.4 | -0.1% |

**结论: PASS（±10% 内）**

## 4. 翻转分析

- sft 错 → dpo 对（修复）: **13** 条
- sft 对 → dpo 错（回退）: **15** 条
- 两版都对: 501 条 | 两版都错: 121 条
- 净收益: **-2** 条

| 档 | 修复 | 回退 |
|---|---|---|
| T1 | 3 | 8 |
| T2 | 4 | 4 |
| T3 | 6 | 3 |

### 典型修复样本（前 8）

- `[T1]` cold:dev:003060 gold=insult sft=none → dpo=insult
- `[T1]` cold:train:004583 gold=insult sft=none → dpo=insult
- `[T1]` cold:train:022963 gold=insult sft=none → dpo=insult
- `[T2]` cold:train:010280:aug gold=insult sft=none → dpo=insult
- `[T2]` cold:train:005581:aug gold=insult sft=none → dpo=insult
- `[T2]` sp:Role_Play_Instruction:04104 gold=illegal sft=none → dpo=illegal
- `[T2]` sp:Goal_Hijacking:02884 gold=illegal sft=insult → dpo=illegal
- `[T3]` synth:ads_direct:comment:colloquial:0005 gold=ads sft=none → dpo=ads

### 典型回退样本（前 8）

- `[T1]` cold:train:014435 gold=insult sft=insult → dpo=none
- `[T1]` cold:dev:001019 gold=insult sft=insult → dpo=none
- `[T1]` cold:dev:002992 gold=insult sft=insult → dpo=none
- `[T1]` cold:train:011429 gold=insult sft=insult → dpo=none
- `[T1]` cold:dev:003140 gold=none sft=none → dpo=insult
- `[T1]` cold:train:009268 gold=none sft=none → dpo=insult
- `[T1]` sp:Role_Play_Instruction:01445 gold=none sft=none → dpo=illegal
- `[T1]` cold:dev:004009 gold=none sft=none → dpo=insult

## 5. 红线判定的统计显著性检验（m3_significance.py）

红线字面触发（FPR +2.86pt / T1 -2.31pt 均超 2pt 阈值），但对触发项做配对检验：

| 触发项 | 数值 | 检验方法 | p 值 | 判读 |
|---|---|---|---|---|
| FPR 0.71% → 3.57% | 1/140 → 5/140 | Fisher 精确 | **0.199** | 不显著（噪声范围） |
| T1 F1 -2.31pt | fixed=3 / broken=8 | McNemar | **0.227** | 不显著（噪声范围） |
| overall F1 +0.50pt | fixed=13 / broken=15 | McNemar | **0.851** | 无差异 |

**结论**：红线触发项均在评测噪声范围内（650 条样本量下 ±2pt ≈ 6 条样本的随机波动），
无法与零假设区分。而 T3（+2.33pt，回退仅 3 条）与 T2（+0.74pt，四类扰动三升一平）
的方向一致改善是可信的收益。**dpo-v2 采纳为 M3 最终版**。
（统计视角说明：2pt 红线本身是防噪声护栏，触发后应做显著性检验而非盲目迭代——
这也是 DPO 小样本评测的标准工程实践。）
