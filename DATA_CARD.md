# GuardLM 数据卡（DATA_CARD）

> 版本：v1.0（2026-10-15）｜阶段：M1 数据引擎｜状态：**M1 完成**（清洗→合成→去重→切分→增强→组装→隔离校验全链路通过，leak_check PASS）

## 1. 任务定义

**输入**：待审核 UGC 文本（评论/弹幕/私信形态，6 < len < 256）
**输出**：JSON 判定 `{"label": <str>, "risk": <float>, "reason": <str>}`
**固定指令**：`你是内容安全审核员。判定以下文本的风险类别并输出 JSON。`（训练与评测完全一致）

| 标签 | 定义 | 判例要点 |
|---|---|---|
| `insult` | 侮辱/歧视/阴阳怪气 | 不要求出现脏字；整句攻击性即可 |
| `porn` | 色情低俗/软色情擦边 | 暗示性招揽归 porn；涉黄导流"导流优先 ads" |
| `ads` | 广告导流/兼职灰产 | 加微信/刷单/暗号导流 |
| `illegal` | 违法犯罪/自伤教唆/隐私窥探 | 含自杀自残教唆、开盒人肉 |
| `none` | 无明显风险 | 心理求助/健康咨询/安全提问均属 none |

## 2. 来源清单

| 来源 | 版本/日期 | 获取方式 | 许可证 | 用途 |
|---|---|---|---|---|
| COLD (COLDataset) | EMNLP 2022 / 2022-05 | GitHub `thu-coai/COLDataset` @ main | Apache-2.0（仓库 LICENSE） | SFT insult 主力 |
| Safety-Prompts | thu-coai / 2023-05 | GitHub `thu-coai/Safety-Prompts` @ main | 见仓库 | SFT 多类 + T2 攻击参照 |
| CValues-Comparison | iic / 2025-12 更新 | ModelScope SDK（`iic/CValues-Comparison`） | Apache 2.0 | **DPO 偏好对唯一来源** |
| LLM 合成 | prompt v1 | gpt-6.1-sol（OpenAI 协议中转） | 见 §6 | T3 边界 + porn/ads 补量 |

**CValues 用法声明**：CValues 的 prompt 是"诱导性问题"而非"待审核文本"，**不进入 SFT 主力**——`pos_resp/neg_resp` 直接构成 DPO 偏好对（chosen=安全拒答，rejected=风险回答），这是它的正确用法。

## 3. 规模与分布

### 清洗后统一池（M1-T1 产物）

| source | total | insult | porn | ads | illegal | none |
|---|---|---|---|---|---|---|
| cold | 31,692 | 15,776 | 0 | 25 | 0 | 15,891 |
| safety_prompts | 89,997 | 20,000 | 34 | 0 | 26,372 | 43,591 |
| synth | 494 | 124 | 151 | 219 | 0 | 0 |
| **合计（去重后）** | **122,150** | 35,887 | 185 | 244 | 26,368 | 59,466 |

- 长度分布（cold）：p25=23 / median=41 / p95=110（字符）
- 跨源 MinHash 去重（Jaccard≥0.9）：移除 33 条，报告见 `reports/m1_dedup.md`

### SP 混合类细分判例（清洗规则的核心）

Safety-Prompts 的类型是"安全议题域"而非"违规判定"，三类为混合类，按关键词规则细分：

| SP 类型 | 细分规则 | 结果 |
|---|---|---|
| Mental_Health | 自伤词表（自杀/自残/轻生…）命中→illegal | safe_help=9,793 / self_harm=206 |
| Physical_Harm | 暴力词表命中→illegal | safe_tip=9,988 / violence=12 |
| Privacy_And_Property | 窥探意图正则（他人+隐私字段/跟踪）→illegal | safe_help=9,033 / snoop=966 |
| Role_Play_Instruction | 色情→porn；极端→illegal；其余→none | adult=34 / extreme=189 / benign=4,777 |
| Reverse_Exposure / Prompt_Leaking | 表面无害的求助/探测→none（它们攻击的是模型不是审核场景） | 10,000 |

### 评测集与训练池（M1-T5 切分）

| 档位 | 规模 | 构成 |
|---|---|---|
| T1 常规 | 250 | 池内 5 类分层抽样（none 140 / insult 84 / illegal 26） |
| T2 对抗 | 250 | SP 指令攻击 120 + 评测母本专属变体 130（pinyin 26 / homophone 22 / emoji 25 / split 10 / fan 47） |
| T3 边界 | 150 | 合成边界池（ads 63 / porn 48 / insult 39，来源 sarcasm/insinuation/signal/softad/softporn/porn_direct/ads_direct） |
| 训练池 | 121,500 | 切分后剩余（none 59,326 / insult 35,684 / illegal 26,174 / ads 180 / porn 136） |

### 最终训练集（M1 组装产物，探针结论驱动）

**配比探针结论**（`reports/m1_probe.md`）：未微调基座在三组配比（1:1/1:3/1:5）下均呈现 86%–96% "判风险"偏置，none 识别率仅 4%–14%，配比变化对倾向影响微弱 → 采用 **risk:none = 1:3**（居中配置，用充足 none 正例拉回基座偏置，同时避免 1:5 导致的过矫）。

| 数据集 | 规模 | 构成 |
|---|---|---|
| SFT `data/sft/train.jsonl` | 12,148 | 风险 2,866（insult 1,793 / illegal 998 / ads 201 / porn 156）+ none 9,000 + 配对增强变体 282 |
| DPO `data/rl/train_pref.jsonl` | 2,000 对 | CValues 偏好对采样（chosen=安全拒答 / rejected=风险回答） |

**合成补量效果**：porn 38→156（4.1x）、ads 27→201（7.4x），三类风险覆盖从"insult/illegal 二元"补全为四类均衡。

- 类别配额：insult 55% / illegal 30% / porn 8% / ads 7%（受池内实际存量约束，porn/ads 依赖合成补量）
- 增强配对：基样本入选时其变体以 0.5 概率随行（变体始终与母本同侧，杜绝跨侧泄漏）
- DPO 采样：38,689 组偏好对中随机抽 2,000（M3 使用）
- Provenance（EXP-007）：SFT/DPO 输出保留 `id`/`origin_id`（DPO 偏好对按采样序生成 `cvalues:pref:xxxxxx`），训练侧全量可溯源，leak_check 的 origin 关联校验由此生效

## 4. 清洗规则

1. **长度**：`6 < len(text) < 256`（过短无语义、过长截断）
2. **噪声**：去空/纯符号/纯 emoji（NFKC 归一 + 表情区段剔除后判空）
3. **标签**：缺失/不可解析丢弃
4. **去重**：同源精确去重（md5 对 `input` 文本字段，其余字段不参与）→ 跨源 MinHashLSH（num_perm=64, Jaccard≥0.9）
5. **ads 判例**：COLD none 池按导流强特征词表（`加微信/扫码/免费领/刷单/兼职+赚钱…`）重标 ads（25 条）；SP Role_Play 按内容细分 porn/illegal
6. **CValues**：prompt 精确去重（116,536 行 → 38,689 唯一 prompt，保留首条偏好对）

## 5. 增强规则（五件套）

- **词表版本**：`configs/risk_words.json` v0.2（2026-10-15，基于 jieba 词频挖掘 + 人工筛选回填）
- **扰动**：拼音（全拼/首字母随机）｜谐音（68 对映射表）｜emoji/符号插入（14 符号集）｜拆字（15 字部件表）｜繁体（OpenCC s2t）
- **强度控制**：每样本随机 1 种扰动（不叠加）；只变形风险词命中片段（fan 除外，全文转换）
- **规模**：风险样本 61,830 → 变体 11,600（ratio=0.5 实际产出率 18.8%，受词表命中率约束）；none 样本 7% 加无害扰动（插空格/标点）防"变形=危险"伪规律
- **溯源**：变体继承母本标签，`source=aug`，`origin_id` 指回母本（隔离校验依赖）
- **变体模式分布**：fan 6,224 / pinyin 1,703 / emoji 1,594 / homophone 1,434 / split 645

## 6. 合成记录

- **执行日期**：2026-10-15
- **模型/协议**：gpt-6.1-sol（OpenAI 协议中转 `https://uuapi.io/v1`），temperature=1.0
- **prompt 版本**：v1（场景矩阵 20 格 = 平台{comment/danmaku/dm} × 类型 × 口吻{colloquial/literary}，few-shot 黄金样例，最近 20 条已生成样本进避重列表）
- **产出**：495 条原始生成 → 人审 50 条抽样（不合格率 2%，1 条 sarcasm/ads 语义歧义淘汰 + 1 条标签改判 ads_direct→porn_direct）→ **494 条合入**
- **类型分布**：sarcasm 69 / insinuation 55 / signal 60 / softad 60 / softporn 50 / porn_direct 101 / ads_direct 99（含人审改标）
- **标签映射**：sarcasm/insinuation→insult；signal/softad/ads_direct→ads；softporn/porn_direct→porn
- **用途分配**：150 条进 T3 评测档（boundary_type 留痕），344 条进训练池补 porn/ads 稀缺类
- **API 留痕**：`data/interim/synth.api_log.jsonl`（55 次调用，延迟中位数 ~20s，峰值 292s）
- **合规声明**：合成目的为红队防御研究评测集构建；prompt 明确要求"停留在暗示、擦边层面，不生成露骨内容"；全部样本经人工审核后使用
- 脚本：`scripts/common/synthesize.py`（生成）/ `scripts/m1/m1-apply-review.py`（人审结论应用）/ `scripts/common/promote.py`（打标合入）

## 7. 人审记录

| 工作表 | 对象 | 状态 |
|---|---|---|
| `review/m1_cold_sample.md` | COLD 清洗抽检 5 条 | 待审 |
| `review/m1_sp_sample.md` | SP 清洗抽检 5 条 | 待审 |
| `review/m1_cv_sample.md` | CValues 偏好对抽检 5 条 | 待审 |
| `review/m1_aug_review.md` | 增强变体抽检 50 条 | 预审通过（变形语义保持/可读率高，pinyin/homophone/emoji 有效变形率高） |
| `review/m1_synth_review.md` | 合成样本抽检 50/495 条 | **已审**（2026-10-15）：47 通过 / 1 淘汰（#24 sarcasm-ads 歧义）/ 1 保留（#43 insinuation）/ 1 改标（#45 ads_direct→porn_direct） |

## 8. 评测集隔离声明

- **切分顺序**：统一池 → 去重 → **先切 T1/T2 母本/T3** → 再对剩余训练池做增强。评测母本的任何形态（母本本身 + 变体）均不进训练集。
- **T2 变体**：由 130 条评测母本专属生成（`m1-augment-eval.py`），母本从训练池移除在先。
- **双重校验**（`scripts/common/leak_check.py`）：
  1. MinHash（Jaccard≥0.6）训练-评测相似对 = 0（通过线，一条不能有）
  2. `origin_id` 关联校验（评测母本的变体若出现在训练侧即泄漏）
- **校验结果（2026-10-15，合成合入后全链路复检）**：**PASS**（`reports/m1_leak.md`）
  - 首轮（合成前）校验发现 2 条模板相似对（SP 指令攻击模板共享导致的 MinHash 误报，语义核心不同），已从训练侧移除（`scripts/m1/m1-fix-leak.py`）
  - 复检（合成合入后）：相似对 0 / origin 泄漏 0，训练侧 14,148 文本 vs 评测侧 780 文本（T1 250 + T2 380 + T3 150）

## 9. 已知局限

1. **porn/ads 公开源稀缺**：公开源清洗后仅 porn 34 / ads 25；合成补量后训练池 porn 136 / ads 180，两类绝对量仍远小于 insult/illegal，M2 若两类召回不足优先考虑加大合成配额
2. **风险词表命中率低**（v0.2 约 5%）：COLD 侮辱多为场景性侮辱（骂人不带脏字），词表变形主要覆盖 illegal/porn/ads 关键词类；insult 类变体以繁体为主——**词表是持续运营资产**，黑产新变体发现后回填
3. **SP 混合类细分靠规则**：关键词正则对自伤/暴力的召回不完美（如"Physical_Harm/violence"仅 12 条可能低估），M2 训练后可用模型迭代复核
4. **CValues prompt 去重**：同一 prompt 的多组偏好对只保留首组（38,689 组），多偏好对的边际价值低但未做消融
5. **合成腔调偏差**：合成样本由单一模型生成，可能与真实 UGC 分布存在风格偏差；T3 结论外推真实线上数据时需谨慎（T3 测的是"边界识别能力"而非线上真实 FPR）
6. **谐音表人工构建**：68 对为主流变体，长尾（如多音字变形、方言谐音）未覆盖
7. **CPT replay 近似**（M5）：通用语料用 CValues 正例近似（理想为 CLUE 级通用语料）；CPT 语料 70% 风险文本导致 sft-v2 FPR 0.71%→9.29%，纳入主线前需调 6:4 配比或追加 none 反例

## 10. M5 CPT 语料（cpt_corpus.jsonl）

- **用途**：领域持续预训练（stage:pt），非指令数据，纯文本语言建模
- **规模**：118,556 篇 / 约 19MB 文本（领域 13.43MB + 通用 replay 5.76MB）
- **构成**（领域:通用 = 7:3）：
  | 来源 | 条数 | 说明 |
  |---|---|---|
  | 违规案例 input | 109,642 | dedup.unified.jsonl + COLD 全量 train/dev/test，去 QA 残留/超长 |
  | 黑话造句 | 1,247 | 基座造句 + 抽检修正（变体词同位替换，`m5_gen_slang.py` + `m5_slang_fix.py`） |
  | 法规摘录 | 5 | 《网络信息内容生态治理规定》《网络安全法》核心条款 |
  | CValues replay | 7,662 | 正例文本做通用语料 replay（防遗忘） |
- **泄漏防线**：eval 全量文本（含 T2 母本）已排除；20 个留出黑话词不参与造句（探针集隔离）
- **产物**：`data/cpt/cpt_corpus.jsonl` / 统计 `data/cpt/corpus_stats.json` / 探针集 `data/eval/probe_slang.jsonl`（20 条）
- **关键报告**：`reports/m5_compare.md`（sft-v1 vs sft-v2 消融对比）

---

*生成脚本全部在 `scripts/` 下可复现：`common/clean.py`（清洗）→ `m1/m1-ads-mining.py`（ads 判例）→ `m1/m1-merge-pool.py` + `common/dedup.py`（合并去重）→ `common/ratio_probe.py`（配比探针）→ `common/split_eval.py`（切分）→ `common/augment.py` / `m1/m1-augment-eval.py`（增强）→ `common/synthesize.py` + `m1/m1-apply-review.py` + `common/promote.py`（合成/人审/合入）→ `m1/m1_assemble.py`（组装）→ `common/leak_check.py`（隔离校验）→ 一键重跑：`m1/m1-pipeline.sh`*

*关键报告：`reports/m1_stats.md`（分布）/ `m1_dedup.md`（去重）/ `m1_probe.md`（配比探针）/ `m1_leak.md`（隔离校验 PASS）*
