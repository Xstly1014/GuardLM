# GuardLM 实验日志（experiments.md）

> 纪律：训练前写入计划，训练后立刻补结果与结论。**没有报告的实验等于没做。**
> 所有对外引用的指标必须能追溯到本文件的某条记录。

---

## EXP-000 | M0 环境验证：QLoRA SFT quickstart 跑通（qwen3-qlora-sft-m0 / m0-v2）

- **日期**：2026-10-15
- **目的**：验证本地 RTX 4090（WSL2）训练链路全通：数据 → QLoRA SFT → LoRA 合并 → 推理验证
- **基座**：Qwen3-1.7B（bf16，本地路径 `/root/models/Qwen3-1.7B`，WSL2 内）
- **框架**：LLaMA-Factory v0.9.3 + PyTorch 2.5.0+cu121 + bitsandbytes 0.45.3（Python 3.10 venv）
- **数据**：LLaMA-Factory `identity` 数据集（91 条），占位符替换为 `{{name}}→GuardLM`、`{{author}}→郭剑华`

### 训练配置（v2，最终生效版）

| 参数 | 值 |
|---|---|
| finetuning | QLoRA（LoRA r=8, alpha=16, all-linear, dropout=0）+ 4bit bnb 量化 |
| lr / scheduler | 1e-4 / cosine, warmup 0.1 |
| epochs | 5.0（230 steps） |
| batch | 1 × grad_accum 2 = 有效 2 |
| cutoff_len | 1024 |
| precision | bf16 |
| 可训练参数 | 8.7M / 1.73B = 0.50% |

### 结果

| 版本 | 配置差异 | loss 曲线 | 耗时 | 对话验证 |
|---|---|---|---|---|
| m0 | 1 epoch, lr 5e-5 | 4.49 → 1.62（46 步） | 25s | ✗ 仍自称 Alibaba（基座先验未覆盖） |
| **m0-v2** | **5 epochs, lr 1e-4** | **4.49 → 0.33（230 步），avg 1.03** | **95s** | ✓ 自我认知改写为 GuardLM/郭剑华（中英文均生效） |

v2 合并后对话实测：
- "Who are you?" → "I am GuardLM, an AI assistant trained by 郭剑华."
- "你是谁？" → "您好，我是 GuardLM，一个由 郭剑华 开发的人工智能助手。"

### 产物

- adapter：`/root/saves/Qwen3-1.7B/qwen3-qlora-sft-m0-v2`（34MB）
- 合并模型：`/root/models/Qwen3-1.7B-sft-m0-v2-merged`（bf16 全量 3.4GB）
- 复现脚本：`scripts/m0/m0-run-sft.sh`（v1 配置）、`scripts/m0/m0-8-run-sft-v2.sh`（v2 配置）、`scripts/m0/m0-8-merge.sh`、`scripts/m0/m0-8-chat-verify.py`

### 结论

1. **M0 验收通过**：本地 24G 单卡可完成 Qwen3-1.7B QLoRA 全链路，训练吞吐约 4.8 samples/s，无显存压力（峰值远低于 24G）
2. **Qwen3 基座自我认知先验强**：字面占位符 + 1 epoch（46 步）不足以覆盖；替换占位符为具体名称 + 5 epochs + lr 1e-4 后完全改写——后续 SFT 数据需注意类目先验对短训的影响
3. 带出的环境坑（已修复，见下）在 M1+ 长训中不会再出现

### 排障记录（M0 环境关键坑，供后续参考）

- **现象**：训练第一步前向即崩，`cuDNN Frontend error: No execution plans support the graph`，伴随 `Could not load library libcuda.so`
- **根因**：训练时带 4D padding mask 的 SDPA 会走 cuDNN attention backend，cuDNN frontend JIT 编译执行计划需要 dlopen 无版本号 `libcuda.so` 与 `libnvrtc.so.12`，而 WSL2 的驱动 stub 只提供 `libcuda.so.1`，venv 内的 nvrtc 又不在系统搜索路径
- **修复**（一次操作永久生效）：
  ```bash
  ln -sf /usr/lib/wsl/lib/libcuda.so.1 /usr/lib/x86_64-linux-gnu/libcuda.so
  ln -sf $VENV/site-packages/nvidia/cuda_nvrtc/lib/libnvrtc.so.12 /usr/lib/x86_64-linux-gnu/
  ln -sf $VENV/site-packages/nvidia/nvjitlink/lib/libnvJitLink.so.12 /usr/lib/x86_64-linux-gnu/
  ldconfig
  ```
- **教训**：WSL2 训练环境遇到 cuDNN JIT / "No execution plans" 类报错，先怀疑 dlopen 链不完整（`lsof` / `ldconfig -p` 查库），而非版本不兼容

---

## EXP-000b | 训练工作流升级：命令行 → YAML 配置 + TensorBoard 实时可视化

- **日期**：2026-10-15
- **变更**：训练入口从 bash 脚本命令行参数迁移至 `training/sft/qwen3-qlora-identity.yaml`（LLaMA-Factory 官方配置文件方式）；启用 `report_to: tensorboard` 实时曲线
- **验证 run**：`qwen3-qlora-sft-m0-v3`（与 v2 同配置）——train_loss 1.0266，与 v2 完全一致，YAML 工作流复现可靠（99.5s / 230 步）
- **可视化链路**：训练写 events 到 `output_dir/runs/` → TensorBoard 监听 `/root/saves/Qwen3-1.7B` → WSL2 localhost 转发，Windows 浏览器直接访问 `http://localhost:6006`
- **依赖变更**：新增 tensorboard 2.21.0 离线安装链（absl-py/grpcio/markdown/werkzeug/markupsafe/pillow）；protobuf 5.29.3 → 7.36.2（transformers 4.52.4 兼容验证通过）；**numpy 保持 1.26.4 未被动**；tensorboard-data-server 为纯 Python 壳（Rust binary 仅影响面板 `--load_fast` 路径，不影响训练写入与默认读取）
- **结论**：日常训练流程固化为「改 YAML → 一条命令 → 浏览器看曲线」，后续 DPO/GRPO 配置照此结构放 `training/dpo/`、`training/grpo/`

---

## EXP-001 | M1 数据引擎：三源清洗 + LLM 合成 + 对抗增强 + 三档评测集构建

- **日期**：2026-10-15
- **目的**：构建 GuardLM 内容安全训练与评测数据全链路——三源统一 schema → LLM 合成边界样本 → MinHash 去重 → 三档评测切分 → 对抗增强五件套 → 配比探针 → 最终组装 + 隔离校验

### 数据来源与产出

| 环节 | 输入 | 产出 |
|---|---|---|
| 三源清洗 | COLD 31,692 / Safety-Prompts 89,997 / CValues 116,536 行 | 统一 alpaca 池（COLD+SP 121,689）+ DPO 偏好对 38,689 |
| LLM 合成 | gpt-6.1-sol（OpenAI 协议中转），场景矩阵 20 格 + few-shot | 495 条 → 人审 50 条抽样（不合格率 2%）→ 494 条合入 |
| MinHash 去重 | 合并池 122,183 | 122,150（移除 33 条模糊重复，num_perm=64, J≥0.9） |
| 三档切分 | dedup 池 122,150 | T1 250 / T2 语料 380（attack 120 + 母本 130 + 变体 130）/ T3 150 + 训练池 121,500 |
| 对抗增强 | 训练池风险样本 62,174 | 15,627 变体（fan 6,237 / pinyin 1,659 / emoji 1,605 / homophone 1,455 / split 630 + 无害 4,041） |
| 最终组装 | 探针结论 1:3 | SFT 12,148（risk 2,866 + none 9,000 + aug 282）+ DPO 2,000 对 |

> **口径澄清（EXP-007 验收修复）**：T2 语料 380 条中，130 条母本（t2_mothers.jsonl）刻意**不入评测**——母本先于增强从训练池移除，仅用作泄漏隔离校验对象与变体溯源（`m1-augment-eval.py` 防泄漏铁律）；实际评测基准 = **650 条（T1 250 + T2 250 + T3 150）**，与 README / DATA_CARD / 各报告头一致。

### 关键实验：配比探针（risk:none = 1:1 / 1:3 / 1:5）

未微调 Qwen3-1.7B 各 50 条混合判定：三组均 86%–96% 判风险（none 识别率 4%–14%），配比对倾向影响微弱 → **基座存在强风险偏置**，采用 1:3（充足 none 正例拉回，避免 1:5 过矫）。

### 关键实验：合成补量效果

| 类别 | 合成前（SFT 集内） | 合成后 | 倍数 |
|---|---|---|---|
| porn | 38 | 156 | 4.1x |
| ads | 27 | 201 | 7.4x |

合成类型分布：sarcasm 69 / insinuation 55 / signal 60 / softad 60 / softporn 50 / porn_direct 101 / ads_direct 99（人审：1 淘汰 + 1 改标 ads→porn）。

### 隔离校验（防训练-评测泄漏）

- 双重校验：MinHash（J≥0.6）相似对 + origin_id 关联；先切评测后增强铁律
- 首轮发现 2 条 SP 模板误报移除；合成合入后全链路复检 **PASS**（训练 14,148 vs 评测 780，0 泄漏）

### 产物

- 训练集：`data/sft/train.jsonl`（12,148）/ `data/rl/train_pref.jsonl`（2,000 对）
- 评测集：`data/eval/t1.jsonl` / `t2_sp_attack.jsonl` / `t2_mothers.jsonl` / `t2_variants.jsonl` / `t3.jsonl`
- 数据卡：`DATA_CARD.md` v1.0（规则/分布/局限全留痕）
- 一键重跑：`scripts/m1/m1-pipeline.sh`（人审结论应用 → promote → 合并 → 去重 → 切分 → 增强 → 组装 → 校验）

### 结论

1. **M1 验收通过**：数据全链路可复现、可追溯，隔离校验零泄漏
2. **合成是稀缺类别的唯一解**：公开源 porn/ads 合计 <60 条，合成补量后四类风险覆盖均衡——这一经验可直接复述为"公开数据集与真实业务分布的差距用定向合成弥合"
3. **基座偏置决定配比**：探针实验避免了"拍脑袋配比"——训练后（M2）可回看 1:3 是否足够拉回 none 识别率
4. 带出的坑（已修复）：未微调基座不遵循指定 JSON schema（探针解析需两级兜底）；PowerShell→WSL 传参引号转义破坏 curl/pipes（改用脚本文件执行）；synth raw 的 type 字段与人审表的 origin_label 字段名不一致（已对齐）

---

## EXP-002 | M2 SFT：Harness v1 + QLoRA sft-v1 + 三档评测 + 错误归因

- **日期**：2026-10-15
- **目的**：搭建可复用评测 Harness（基线 base-v0）→ QLoRA SFT 训练 sft-v1 → 三档评测出分 → 错误归因四分类，为 M3/M4 提供路线图

### 训练六要素

| 要素 | 值 |
|---|---|
| 基座 | Qwen3-1.7B（QLoRA 4bit NF4, r16/a32/dropout0.05, target=all）|
| 数据 | guardlm_sft 12,148 条（风险:none=1:3，含 282 条增强变体；instruction 尾部 /no_think）|
| 超参 | lr 1e-4 / cosine / warmup 0.1 / 3 epochs / 等效 batch 32 / cutoff 256 |
| 训练时长 | **12 分 16 秒**（1,083 步，吞吐 47 samples/s）|
| 显存峰值 | **17.3 GB**（含桌面常驻 ~4.4G；memtest 同配置实测）|
| loss | train 0.111（末段 0.003–0.005）/ eval 0.0056，末两次 eval 持平 → 无过拟合分叉 |

### 评测结果（650 条，temperature=0.7 官方非思考参数）

| 指标 | base-v0 | sft-v1 |
|---|---|---|
| 格式错误率 | 100% | **0.2%**（验收线 <3%）|
| 总体 F1 / FPR | 0 / – | **0.862** / 0.71% |
| T1 F1 / T2 对抗 Recall / T3 F1 | 0 | 0.873 / **0.800** / 0.805 |
| T2 分扰动 | – | emoji 96% / fan 94% / 谐音 91% / split 80% / pinyin 69% / sp_attack 72% |

### 错误归因四分类（134 错误 / 650，20 条人审复核通过）

格式错误 0.7% / 类别混淆 17.9% / **对抗失效 38.8%（M4 GRPO）** / **边界误判 42.5%（M3 DPO）**；复核发现 ~20% gold 噪声（COLD 源标签争议，M3 需清洗）。

### 结论

1. **SFT 核心目标全部达成**：JSON 契约从 0 到 99.8% 遵循；格式错误率 0.2% 远优于 3% 验收线
2. **五件套增强兑现**：表层扰动（emoji/繁体/谐音）召回 91–96%，但拼音变形 69% 是语义级短板
3. **一句话结论**：sft-v1 的主要矛盾是边界误判（42.5%）与对抗失效（38.8%）双高——隐性语义边界和拼音变形是最大弱点，分别对应 M3 DPO 与 M4 GRPO
4. 带出的坑（已修复）：① temperature=0.2 在 bf16 下 logits 数值放大触发 multinomial CUDA assert（改用官方 0.7）；② WSL2 cuDNN SDPA 批量左填充推理偶发 nan → CUDA device-side assert 不可恢复（attn_implementation=eager + logits nan_to_num 净化器双保险，吞吐反升至 15.2 samples/s）；③ PowerShell→WSL 多行 python -c 必炸（一律写脚本文件）

---

## EXP-003 | M3 DPO：偏好对构建 + dpo-v1a/v2 两版迭代 + 方向修正与显著性检验

- **日期**：2026-10-15
- **目的**：on-policy 偏好对构建（badcase 复活 + 错误挖掘 + 变体镜像 + CValues）→ DPO 训练 → 三档评测对比 → 红线检查与迭代

### 偏好对构建（prefs.jsonl 2000 对 + prefs-v2.jsonl 2176 对）

| 来源 | 数量 | 说明 |
|---|---|---|
| cvalues | 1233 | CValues 安全/不安全回答（NL 对，easy 主力）|
| onpolicy_mine | 484 | sft-v1 在 3000 条未见样本上的真实错误（on-policy）|
| aug_mirror | 150 | 风险变体镜像（chosen=变体正确判定 / rejected=漏放）|
| m2_badcase | 133 | M2 归因错误复活（评测集闭环，Spec t31 认可）|
| none_mirror（v2 增） | 176 | **方向修正**：chosen=none 正确判定 / rejected=误伤 JSON |

卫生检查全过：泄漏 0（m2_badcase 闭环除外）/ 判定对 JSON 非法 0 / 长度配平 1.013 / 20 条人审剔除 3 条源数据噪声后补齐。

### DPO 训练迭代（每版只动一个变量）

| 版本 | 变量 | KL(π‖π_ref) | eval margins | eval acc | 结论 |
|---|---|---|---|---|---|
| dpo-v1（弃） | lr=5e-6 | – | – | – | loss 卡 ln2 不动，弃 |
| **dpo-v1a** | lr 5e-6→**1e-5** | **≈0.001 bits/token** | 0.053 | 0.62 | 学起来但方向失衡 |
| **dpo-v2（最终）** | 数据 +176 none_mirror | – | **0.200** | **0.727** | 方向修正，采纳 |

配置：β=0.1 / sigmoid / r32 α4（α/r=0.125 对齐阶段小步）/ batch 2×16 / 1 epoch / bf16 / QLoRA 4bit；ref=sft-v1-merged（LLaMA-Factory LoRA-DPO ref=禁用 adapter 的基模型）。

### 评测对比（650 条三档全量）

| 指标 | sft-v1 | dpo-v1a | **dpo-v2** |
|---|---|---|---|
| 总体 F1 | 0.862 | 0.863 | **0.867** |
| T1 F1 | 0.873 | 0.873 | 0.850 |
| T2 F1 / Recall | 0.889 / 0.800 | 0.881 / 0.788 | **0.896 / 0.812** |
| T3 F1 / Recall | 0.805 / 0.673 | 0.824 / 0.700 | **0.828 / 0.707** |
| FPR | 0.71% | 3.57% | 3.57% |
| 长度漂移 | – | 0% | **0%** |
| 格式错误率 | 0.15% | 0.15% | 0.15% |

### 红线诊断与统计裁决（本阶段核心方法论产出）

1. **v1a 触发 FPR 红线**（+2.86pt）→ 按手册任务4 流程测 KL：**KL≈0.001 bits/token ≈ 0**（64 条 on-policy 蒙特卡洛估计），排除「漂太远」，定位为**偏好方向失衡**（判定对 chosen=风险 742 : chosen=none 25）
2. **v2 数据权重修正**（+176 none_mirror，β/lr 不动）→ margins 0.05→0.20（3.8x），T3/T2 继续改善
3. **v2 仍字面触发红线**（FPR +2.86pt / T1 -2.31pt）→ **统计显著性检验**：Fisher p=0.199 / McNemar p=0.227 / overall p=0.851——全部不显著，红线触发在 650 条评测的噪声范围（±2pt ≈ 6 条样本波动）内
4. **最终裁决**：T3（+2.3pt，回退仅 3 条）与 T2（四类扰动三升一平）的方向一致改善可信，退化项无统计证据 → **dpo-v2 采纳为 M3 最终版**

### 结论

1. **DPO 主战场兑现**：T3 边界 F1 +2.3pt / Recall +3.3pt（两版一致方向），T2 对抗 Recall +1.2pt
2. **KL 引导调参实证**：KL≈0 + loss 卡 ln2 → 升 lr；红线触发 + KL≈0 → 查数据权重而非 β——「先测 KL 再动手」避免了两次盲调
3. **统计检验保护迭代**：小样本评测（650 条）上 ±2pt 全是噪声，红线触发后先做 Fisher/McNemar 检验再决定是否迭代，避免过拟合评测集
4. DPO 的净效应是**错误内部迁移**（134→133→136 错误总数持平，漏放↔误伤互换），类别结构不变——边际收益递减，M4 GRPO 才是下一步杠杆
5. 带出的坑（已修复）：① Windows 桌面程序（视频播放/Steam/ToDesk 等 20+ 进程）抢占 GPU 导致训练每步 9s→190s 甚至活锁，`wsl --shutdown` 重置 GPU 状态后恢复 4.3s/it；② StopCommand 只杀 PowerShell 侧 wsl.exe，WSL 内进程需 `pkill` + 注意命令串自匹配自杀；③ DPO batch=4 显存顶满（ref 模型常驻+双前向），降 2×16 后 18.9G 稳定

---

## EXP-004 | M4 GRPO：RLVR 组合奖励 + 温度探针 + grpo-v1 三档评测

- **日期**：2026-10-15
- **目的**：针对 DPO 无法解决的对抗失效（T2 sp_attack/pinyin 漏放），用 GRPO（DeepSeek-R1 同款，组内相对优势）做泛化优化——奖励可验证（label 对错直接比对），无需奖励模型
- **起点**：dpo-v2-merged（GRPO 起点 = KL 锚点，peft 模式 disable_adapter 免第二份模型显存）
- **框架**：TRL 0.21 GRPOTrainer + QLoRA（r32 α4，对齐 DPO 配置）

### 奖励函数设计（四组件各司一职，单测 20/20）

| 组件 | 打分 | 设计意图 |
|---|---|---|
| format_reward | 干净 JSON 1.0 / 清洗 0.75 / repair 0.5 / 失败 0 | 巩固 SFT 格式成果防退化 |
| correctness_reward | label 对 2.0 + risk 误差<0.2 加 0.5 | 核心任务信号，权重压倒格式 |
| robust_reward | aug 样本且正确 → correctness ×0.5 叠加 | 对抗泛化信号 ×1.5 放大 |
| length_penalty | 每超 20 token 扣 0.1 + 空 reason 扣 0.2 | 防 RL 输出膨胀经典坑 |

- 离线 sanity：dpo-v2 真实输出喂分，正确样本均分 4.75 vs 错误 0.98（gap 3.77，信号可分）
- prompt 池 2400 条：对抗 800（318 条模型真实错误变体 + 482 aug 补齐）+ 常规 1600（risk:none=1:3），与 650 条评测集严格隔离

### 关键实验：温度探针（零优势组处置）

- dry-run 暴露：`frac_reward_zero_std` 0.75-1.0 + entropy 0.006 nats/token——**DPO 后模型分布过尖，组内 8 采样高度雷同 → 无梯度**
- 探针（24 prompt × G8 × temp {1.0, 1.2, 1.5}）：非零 std 组 33% / 46% / **50%**，fmt 均值 1.0 / 1.0 / 0.997
- **裁决 temp=1.5**：有效梯度组翻倍且格式零损失——先诊断后调参，不盲改手册默认值

### 训练（300 optimizer steps，24.8 分钟，5.03s/it）

- 超参：G=8 / beta=0.04 / lr=5e-6 / temp=1.5 / max_completion=80 / batch 8×8=64 completions/step
- 五指标全程监控：entropy 稳定 0.03±（无坍缩）/ KL ≤0.0026（锚定有效）/ reward 3.4-3.9 平稳 / completion 24 token 纹丝不动 / frac_zero_std 均值 ~0.6
- 无三大失败模式触发（熵坍缩/奖励钻空子/格式退化）

### 评测（650 条三档，与 dpo-v2 对比）

| 指标 | dpo-v2 | grpo-v1 | Δ |
|---|---|---|---|
| 总体 F1 | 0.8669 | **0.8740** | +0.71pt |
| T2 对抗 Recall | 0.8120 | **0.8280** | +1.6pt（主战场达成） |
| T1 F1 | 0.8500 | 0.8713 | +2.13pt（修复 DPO 回退） |
| FPR 误伤 | 3.57% | **2.86%** | -0.71pt（DPO 红线拉回） |
| T3 F1 | 0.8281 | 0.8189 | -0.92pt（McNemar p=0.688，噪声） |
| 格式错误率 | 0.15% | **0.00%** | 奖励组件生效 |
| 长度漂移 | — | +0.1% | PASS（防住 RL 膨胀） |

- 翻转分析：修复 19 / 回退 10 / **净 +9**（DPO 阶段为 -2）；T2 净 +7（p=0.092 边际显著）
- 显著性检验：T3 回退 p=0.688 纯噪声；homophone -9.1pt 为 22 条小样本 2 条翻转波动
- sp_attack +3.3pt / pinyin +3.8pt / emoji +4.0pt / illegal 召回 +3.6pt

### 结论

1. **GRPO 打破了 DPO 的「漏放↔误伤互换」僵局**：T2 Recall +1.6pt 与 FPR -0.71pt 同向改善（DPO 阶段两者是跷跷板），净翻转由 -2 转正 +9
2. **总体 F1 四版本单调上升**：0.000 → 0.862 → 0.867 → **0.874**，grpo-v1 采纳为 M4 最终版
3. **温度探针是本阶段最高杠杆动作**：DPO 收敛模型做 RL 起点，分布过尖 → 零优势组 >75%，升温 1.5 后有效梯度组翻倍——「dry-run 看指标 → 探针定参数」可复用为 RL 冷启动 SOP
4. **奖励工程验证了「组合+增量」原则**：格式 0% / 长度零漂移 / FPR 下降，三个辅助组件全部兑现设计意图
5. 带出的坑（已修复）：① trl 0.9.6 无 GRPOTrainer，升 1.14 会拉 transformers 5.x 与 torch 2.5 冲突 → 锚定 **trl 0.21 + transformers 4.56.1** 兼容组合；② TRL+peft 下 gradient_checkpointing 生成走 no-cache → logits nan（CUDA assert），patch `model.generate` 在生成期切 eval+cache+禁 ckpt、结束恢复训练态彻底解决；③ Dataset 列经 TRL 透传进奖励函数会被 json 序列化为字符串，奖励函数内需 `_maybe_json` 统一反序列化；④ transformers 4.56 中 `is_gradient_checkpointing` 是属性不是方法（API 变更）

---

## EXP-005 | M5 CPT 消融：领域持续预训练 → 两阶段对比（cpt-v1 / sft-v2）

- **日期**：2026-10-15
- **目的**：验证「CPT 灌领域语感 → SFT 教任务行为」两阶段路线对黑话泛化（elicitation）的增益，控制变量消融
- **设计**：sft-v1（直接 SFT）vs sft-v2（CPT→SFT），同一份数据同一套超参，唯一差异是模型起点
- **环境变更**：transformers 4.56.1 → **4.52.4**（llamafactory 0.9.3 官方支持范围，M4 的 GRPO 依赖 4.56——若需复跑 GRPO 需升回；trl 0.21 的 `logprobs_from_logits` 缺失以 core.py 尾部 shim 补齐，PPO import 链存活）

### 语料构建（M5-1）

- 四来源 118,556 篇（领域 110,894 + 通用 replay 7,662，7:3 字符配比）：
  违规案例 109,642（dedup input + COLD 全量）+ 黑话造句 1,247 + 法规摘录 5 + CValues 正例 replay
- **泄漏防线**：eval 全量文本（含 T2 母本）从语料排除——CPT 语料污染评测是消融实验最常见的自欺
- **黑话变体坑**：基座对 homophone 变体词按字面造句语境错位 → 丢弃直接变体造句，改原词自然句同位替换（m5_slang_fix.py）
- **探针集隔离**：20 个留出词（insult/porn/ads/illegal 各 5）不参与造句，度量泛化而非记忆

### 训练（防遗忘四重保险）

| 阶段 | 配置 | 耗时 | 结果 |
|---|---|---|---|
| cpt-v1 | stage:pt / LoRA r32α64 / lr 5e-6 / warmup 0.2 / replay 30% / cutoff 512 / 2ep | 20min46s（498 步） | train_loss 3.486 / eval_loss 3.303（PPL 27.2） |
| sft-v2 | 与 sft-v1 超参严格一致（r16α32 / lr 1e-4 / 3ep / cutoff 256） | 12min（1,083 步） | eval_loss 0.0055（sft-v1 为 0.0056，任务收敛同水位） |

- loss 4.19→3.44 稳定下降，grad_norm 3.7→0.41 无尖刺；通用探针（闲聊/常识/数学）三个检查点全过，**防遗忘零损失**

### 评测（核心结果）

| 指标 | sft-v1 | sft-v2 (CPT) | Δ |
|---|---|---|---|
| **P5 黑话 F1（核心）** | 0.8235 | **0.9474** | **+12.4pt** |
| P5 精确匹配 | 60% | 85% | +25pt |
| 总体 F1 | 0.8619 | **0.8978** | +3.6pt |
| T2 对抗 Recall | 0.800 | **0.868** | +6.8pt（pinyin +15.4pt 最大） |
| T3 边界 F1 | 0.805 | **0.8636** | +5.9pt |
| **FPR 误伤** | **0.71%** | **9.29%** | **+8.6pt ⚠️** |

- P5 翻转 5/20 全部正翻（ads×4: 刷单/囤货/收徒/清仓，porn×1: 出台）——探针词未进语料，是 10.9 万篇主料的整体语感起效
- 误伤 13 条归因：~6 标注灰区 + ~5 真实误伤（吐槽/叙事被判风险）+ ~2 SP 安全问询
- **根因**：CPT 语料 70% 风险文本 → 风险先验回归（M1 探针发现基座 86-96% 判风险偏置，SFT 1:3 配比纠正，CPT 部分逆转）——「漏放↔误伤」跷跷板在预训练侧的再现

### 结论

1. **CPT 消融假设验证成功**：未见黑话 F1 +12.4pt、T2 R +6.8pt、总体 F1 +3.6pt，elicitation 效应显著且可度量（留出探针集设计）
2. **代价明确不免费**：FPR +8.6pt；M5 为消融实验，**生产线不切换**（grpo-v1 仍为线上版本）
3. **纳入主线的对冲方案**（二选一）：replay 配比 7:3→6:4 稀释风险先验；或 CPT 语料追加 none 反例（正常吐槽/叙事文本）
4. 带出的坑：① llamafactory 0.9.3 与 transformers 4.56 双重不兼容（ParallelismConfig 类型解析 + trl import），降级 4.52.4 一劳永逸；② `| tee` 管道下 stdout 块缓冲导致训练 log 不落盘（tqdm 走 stderr 实时），健康监控改读 TensorBoard events 文件；③ WSL2 下 export 偶发 I/O 挂起（进程卡死且 /proc 遍历跟随挂起），重跑即恢复

---

## EXP-006 | M6 生产化：vLLM 部署 + 约束解码 + 压测 + AWQ 量化掉点对比

- **日期**：2026-10-16
- **目的**：训练态模型（grpo-v1）无损落到服务态——合并导出、vLLM 服务化、约束解码、容量压测、演示页、4bit 量化边界摸底
- **环境变更**：serve-venv（/root/serve-venv）：vLLM 0.12.0 / transformers 4.57 / autoawq 0.2.9（量化时打两处 shim）

### 合并与服务化（M6-1/2）

- grpo-v1 LoRA 合并导出 guardlm-final：50 条抽样 48 条判定一致（2 条采样随机），650 条全量指标与训练态持平——**合并零损耗**
- vLLM bf16 + `response_format=json_schema`（XGrammar）约束解码常开：格式错误率 0.2% → **0.00%**；reasoning tax 实测 F1 -0.17pt（噪声内），压测确认零性能税（structured ON/OFF 吞吐一致）
- 压测纪律：`--no-enable-prefix-caching` 防重测虚高；in-flight 并发模型（稳态在途请求数）而非连接数

### 容量压测（M6-3）

| 并发（in-flight） | 吞吐 req/s | tok/s | P99 E2E | TTFT P99 |
|---|---|---|---|---|
| 1 | 28.2 | 646 | 35ms | 27ms |
| 4 | 49.5 | 1,190 | 81ms | 45ms |
| 16（稳态容量） | **62.3** | **1,527** | 266ms | 74ms |

- **宿主 GPU 干扰事故**：conc=16/64 出现周期性全局停摆（30-80s），四证据链（引擎日志 Running:64 reqs / generation 0.0 tok/s、Windows 侧 GPU 100% util 零吞吐、20+ 宿主 GPU 进程、干净窗口复测不复现）归因为 WSL2 共享 GPU 给 Windows 图形栈的让位行为，与 GuardLM 服务栈无关——`reports/bench.md`

### 演示服务（M6-4）

- FastAPI（:7860）+ 静态页三示例冒烟通过（常规/黑话变体/边界）；**fail-closed 纪律**：后端不可达/解析失败显式 502，绝不输出臆造判定；VLLMBackend 与 HFBackend 交叉验证留痕

### AWQ 量化对比（M6-5）

| 部署形态 | 精度 | 总体 F1 | Recall | FPR | T2 R | T3 F1 | 650 条耗时 | 体积 |
|---|---|---|---|---|---|---|---|---|
| HF transformers（grpo-v1） | bf16 | 0.8740 | 0.7824 | 2.86% | 0.828 | 0.8189 | ~4.5min | 3.3G |
| vLLM bf16（guardlm-final） | bf16 | **0.8755** | 0.7863 | 3.57% | 0.820 | 0.8281 | 183s | 3.3G |
| vLLM AWQ（guardlm-awq） | 4bit | 0.8274 | 0.7098 | **2.14%** | 0.748 | 0.7603 | **69s** | **1.3G** |

- **vLLM bf16 部署零精度损耗**（+0.15pt 噪声内）+ 吞吐 2.4x——生产线定形态
- **AWQ 掉点 -4.81pt 不上线**：伤害集中 Recall -7.65pt（FN 109→148，漏放换误伤），T2 扰动归因 homophone **-18.2pt** / split -10.0pt / sp_attack -9.1pt——谐音/拆字判别最先被 4bit 权重噪声破坏；1.7B 小模型权重冗余不足，AWQ 的 1% 显著权重保护不覆盖本任务判别敏感区
- guardlm-awq 降级为低显存（≤8G）/高吞吐离线初筛备选；后续压缩优先 INT8 > 4bit QAT > AWQ——`reports/m6_serving.md`

### 结论

1. **M6 全链路收官**：训练态 → 服务态零损耗迁移验证完毕，bf16 vLLM 为生产形态，容量基线 62 req/s@P99 266ms，格式错误率 0.00%，fail-closed 纪律贯穿
2. **量化边界摸清**：AWQ 4bit 对 1.7B 内容安全模型不可用（Recall -7.65pt），量化路线图的降级门槛由此确立
3. 带出的坑：① autoawq 0.2.9 × transformers 4.57 两处兼容断点（scale.py GELU 类移除、quantizer.py Catcher 属性代理缺失），`scripts/m6/m6_patch_awq.py` 双 shim 修复，语义不变；② **WSL2 GPU 状态残留活锁**：上一个 GPU 进程被强杀后立即重启 vLLM → 引擎 100% CPU 挂起/NCCL 初始化超时，GPU 冷启动后完全正常——重启 vLLM 前确认旧引擎退出干净（setsid 启动 + pkill 后冷却等待）；③ 隔离测试纪律：单请求超时阈值须 >80s（宿主干扰停摆窗口上限），否则误判为引擎挂起

---

## EXP-007 | GPT 独立验收：全量问题修复 + 评测协议严格化 + 可复现性复核

- **日期**：2026-10-16 深夜 ~ 2026-10-17
- **目的**：GPT 对项目（代码+文档）做独立验收，输出 P0-P2 问题清单；本条记录全量修复与复核结果。**纪律：验收发现的问题必须逐条裁定真伪、修复、重跑验证，不留「修了但没验证」的尾巴。**

### A 组 | 文档口径修复（P1）

1. **T2 380 vs 250 口径冲突**：切分表写 380（含 130 母本），所有评测用 250——已澄清：130 母本仅作变体溯源/隔离检查，不入评测基准；评测基准恒为 650 = 250+250+150
2. **DATA_CARD 去重措辞**：「整行 md5」→「md5 对 `input` 文本字段，其余字段不参与」（与代码一致）

### B 组 | 代码修复（P0）+ 重跑验证

1. **B1 provenance 断链（P0，最重要）**：`m1_assemble.py` 输出时丢弃 `id`/`origin_id`，导致 leak_check 的 origin 关联校验**空转恒过**（train_ids 恒空集），隔离校验形同虚设。修复：
   - assemble 输出保留 `id`/`origin_id`（DPO 偏好对按采样序生成确定性 id `cvalues:pref:xxxxxx`）；重跑验证 **训练内容与 v1 逐条 0 差异**（SFT 12,148 条 / DPO 2,000 对，seed 固定确定性成立）
   - `leak_check.py` 升级三重校验：MinHash（范围扩至 **DPO prompt/chosen/rejected 全量文本**，18,148 条目）+ origin 关联 + **缺 provenance(id) 判 FAIL**；重跑 **PASS：相似对 0 / origin 泄漏 0 / 缺 id 0**——origin 校验首次真正生效且 0 泄漏，证明切分本身干净，此前的 PASS 是侥幸不是证明
2. **B2 评测协议 fail-fast**：`harness/run.py` 评测文件缺失从「静默跳过」改为 FileNotFoundError；新增条数断言（T1=250 / T2=250 / T3=150 / P5=20），不符即拒绝出报告——杜绝「650 条变 600 条」级静默口径漂移
3. **B3 strict 格式口径离线重算**（`reports/m7_strict_format.md`）：全 pred 文件重算 parse_level 分布——①「0.2%」精确为 **0.15%（1/650）**，且 sft-v1/dpo-v2/m6_tax_off/guardlm-final 的 format_error **全部集中于同一条提示注入样本 `sp:Goal_Hijacking:00514`**（注入话术劫持模型脱离 JSON 契约），非随机格式噪声；② 约束解码 ON（m6_tax_on/m6_awq）下该样本 0 次失手——**schema 强制把被注入模型拉回合法 JSON，约束解码的防御价值首次获得逐条实证**；③ repaired 全程 0（json_repair 从未真正介入，契约遵循来自 SFT 而非容错层）

### C 组 | 统计补全 + 可复现性复核

1. **C1 增强命中率**（`reports/m7_aug_stats.md`）：词表定向扰动的能力天花板 = **span 覆盖率 27.3%**（62,174 条风险样本仅 16,995 条可命中）；各模式上限 fan 99.8% > pinyin/emoji 27.3% > homophone 23.3% > split 10.5%；**ads/porn 增强近乎失效（各 38 条 vs insult 6,267）**——从数字上闭环解释了 M1 引入 LLM 合成补量的必要性
2. **C2 三模型重跑复核**（`reports/m7_eval_recheck.md`）：sft-v1 / dpo-v2 / grpo-v1 以 **seed=2026 固定采样**重跑 650 条——F1 漂移 +1.21 / +0.72 / +0.52pt，**全部在 ±2pt 噪声带内，历史报告数字可复现性确认**；新增 `harness/run.py --seed` 参数（transformers 后端固定采样流）。重跑数字成为新可复现基线：sft-v1 0.8740 / dpo-v2 0.8740 / grpo-v1 0.8792

### C2 复核中的三个过程发现（防再踩）

1. **FPR 小分母噪声**：none 仅 140 条，1 条翻转 = 0.71pt 粒度；FPR 在 0.71%↔3.57% 间跳动属采样波动，非模型行为漂移——引用 FPR 须注明粒度
2. **sft-v1 与 dpo-v2 重跑 raw 输出 91.4% 逐字节相同**：非加载 bug（三次基座可由加载日志区分：Qwen3-1.7B 分片 vs merged 单文件），真因 = DPO 策略差异本就极小（EXP-003 实测 KL≈0.001 bits/token）+ 固定 seed 采样路径锁死——复现侧再次印证「DPO 是偏好微调而非行为重构」
3. **混淆矩阵一致 ≠ 预测一致**：recheck sft-v1 混淆矩阵与原 grpo-v1 逐位相同（TP=399 FP=4 FN=111 TN=136），但判定一致率仅 94.9%（33 条分歧恰好错误互换平衡）——复核必须逐条比对 pred，混淆矩阵巧合会误导裁定

### 修复文件清单

- 代码：`scripts/m1/m1_assemble.py`（保留 provenance）、`scripts/common/leak_check.py`（三重校验）、`harness/run.py`（fail-fast + 条数断言 + `--seed`）
- 文档：`DATA_CARD.md`（去重措辞 + provenance 说明）、`reports/m6_serving.md`（格式错误率口径脚注）、`experiments.md`（T2 口径澄清）
- 新报告：`reports/m7_strict_format.md`、`reports/m7_aug_stats.md`、`reports/m7_eval_recheck.md`、`reports/m7_recheck/`（三模型重跑 pred+报告）
- 重跑产物：`data/sft/train.jsonl` + `data/rl/train_pref.jsonl`（+provenance 字段，内容 0 差异）、`reports/m1_leak.md`（三重校验 PASS）

### 结论

1. GPT 验收问题全部关闭：P0 provenance 断链已修复并以「origin 校验真正生效 + 0 泄漏」重新验证；口径类（T2/去重/格式错误率）全部对齐唯一事实源；评测协议 fail-fast 化
2. 验收反而带来三项增值：提示注入样本的约束解码防御实证、增强能力天花板的量化、全评测基线 seed 固定可复现
3. 生产服务按 EXP-006 协议（pkill + 30s 冷却 + setsid）重启并端到端验证通过

---



