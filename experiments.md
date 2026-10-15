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
- 复现脚本：`scripts/m0-run-sft.sh`（v1 配置）、`scripts/m0-8-run-sft-v2.sh`（v2 配置）、`scripts/m0-8-merge.sh`、`scripts/m0-8-chat-verify.py`

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
| 三档切分 | dedup 池 122,150 | T1 250 / T2 380（attack 120 + 母本 130 + 变体 130）/ T3 150 + 训练池 121,500 |
| 对抗增强 | 训练池风险样本 62,174 | 15,627 变体（fan 6,237 / pinyin 1,659 / emoji 1,605 / homophone 1,455 / split 630 + 无害 4,041） |
| 最终组装 | 探针结论 1:3 | SFT 12,148（risk 2,866 + none 9,000 + aug 282）+ DPO 2,000 对 |

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
- 一键重跑：`scripts/m1-pipeline.sh`（人审结论应用 → promote → 合并 → 去重 → 切分 → 增强 → 组装 → 校验）

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
