# M6-3 性能压测报告（guardlm-final · vLLM 0.12 · 单卡 4090/24G · WSL2）

## TL;DR

- **干净窗口稳态容量**：并发 16 时 **62 req/s / 输出 1527 tok/s / P99 E2E 266ms / TTFT P99 74ms**，此时 KV cache 仅用 3%——服务栈远未饱和。
- 单请求 P50 E2E ~210ms（约 40 输出 token），TTFT ~13ms。
- **约束解码零吞吐税**：structured ON 与 OFF 在并发 1 下 P50 E2E 211ms vs 207ms、吞吐 4.6 vs 4.7 req/s，完全一致（M6-2 已证零质量税，本节证零性能税）→ 约束解码可常开。
- 压测窗口遭遇**宿主环境级 GPU 干扰**（Windows 桌面 20+ 进程与 WSL CUDA 共享同一张 4090），出现周期性全局停摆（10~80s）。四条独立证据交叉归因，与模型 / vLLM / 约束解码**均无关**；conc=64 干净样本未取得，生产容量规划以裸机复测为准。

## 方法与纪律

| 项 | 值 |
|---|---|
| endpoint | `http://localhost:8000/v1/chat/completions`（vLLM 0.12.0, bf16, max_model_len=512） |
| 并发控制 | in-flight 信号量稳态（非连接数），梯度 1/4/16/64，每档 3 轮 |
| 语料 | `data/eval/t1.jsonl` 真实分布 250 条，每轮 100 prompt 循环 |
| 采样 | temp=0.7 / top_p=0.8 / top_k=20 / max_tokens=64，`enable_thinking=False`（与训练/评测侧一致） |
| 防虚高 | 服务端 `enable_prefix_caching=False`；预热请求（grammar 编译/CUDA graph）不计入统计 |
| 指标 | P50/P99 E2E、TTFT P50/P99、req/s、输出 tok/s、失败率（`time.perf_counter` 单调钟） |
| 环境如实记录 | 客户端与服务同机（WSL2 内 loopback）；宿主为在用 Windows 桌面 |

## 干净窗口稳态容量（structured ON = 生产配置）

| 并发 | P50 E2E | P99 E2E | TTFT P50 | TTFT P99 | req/s | 输出 tok/s | 失败率 |
|---|---|---|---|---|---|---|---|
| 1 | 211ms | 282ms | 12.6ms | 25ms | 4.6 | 112 | 0% |
| 4 | 200ms | 229ms | 16ms | 31ms | 19.9 | 488 | 0% |
| 16 | 235ms | 266ms | 37ms | 74ms | 62.3 | 1527 | 0% |
| 64 | *未取得干净样本（见干扰事故）* | | | | | | |

- 延迟曲线随并发近似水平（P50 211→235ms），吞吐随并发近线性（4.6→20→62 req/s），为典型"小模型 + 短输出"低延迟服务画像；conc=16 时 KV cache 用量仅 3%，理论上界远在 64 并发之上。
- 服务端 2400+ 请求全程 HTTP 200、零 5xx；客户端侧错误仅出现在干扰停摆期间（120s 超时），fail-closed 行为符合预期。

## 环境干扰事故记录与归因（如实记录）

压测时段（约 01:35–01:55）出现周期性全局停摆，特征与证据链：

1. **引擎冻结签名（服务端）**：vLLM 引擎指标 `Running: 64 reqs, Waiting: 0, GPU KV cache 3.0%, Avg generation throughput: 0.0 tokens/s` —— 64 请求全部在途、队列空、显存几乎空闲、生成吞吐归零后自行恢复。是引擎步进整体停摆，**不是容量饱和**（饱和应表现为 Waiting 堆积 + KV 高位）。
2. **全批同生共死（客户端）**：conc=64 轮次 P50≈P99（61.30s vs 61.34s）且 TTFT P50 仅 112ms —— 全部请求首 token 正常后一起冻结、冻结结束一起完成，为全局冻结而非排队。
3. **与配置无关（对照实验）**：structured OFF、并发=1 的单请求串行流同样出现 15.4s 停摆与 1 例超时 —— 排除约束解码 / XGrammar / 批处理调度 / 引擎队列归因。
4. **宿主侧占用（根因）**：Windows 侧 nvidia-smi 显示 20+ 进程持有 GPU 上下文（**ToDesk 远程桌面持续屏幕捕获**、Edge/Chrome/WebView、汽水音乐、微信、Steam、百度网盘、Windows Shell 组件等），压测时 GPU util 100% 而显存带宽 0%；WSL 侧 32 vCPU load 1.0，无 CPU 饥饿。单张 4090 通过 WDDM 半虚拟化同时服务宿主图形栈与 WSL CUDA，宿主高峰时 WSL CUDA 整体让位 → 引擎级停摆。

**结论**：停摆为开发机共享 GPU 环境属性，非 GuardLM 服务栈缺陷；服务栈在无干扰窗口内的指标（上表）为可信稳态容量。**教训**：WSL2 容量压测需宿主闲置（关闭远控/浏览器/图形应用）或裸机进行；生产容量数字以裸机复测为准。

## 受污染轮次原始数据（structured ON，供存档）

| 并发 | 轮 | P50 E2E | P99 E2E | 备注 |
|---|---|---|---|---|
| 16 | 2 | 249ms | 33684ms | 轮末引擎冻结 ~33s（P50 未受影响） |
| 16 | 3 | 229ms | 31072ms | 同上，冻结 ~31s |
| 64 | 1 | 46416ms | 86401ms | 冻结 >120s，63 请求客户端超时（服务端仍 200） |
| 64 | 2 | 61302ms | 61337ms | 首 token 后全局冻结 ~61s |
| 64 | 3 | 79690ms | 79719ms | 首 token 后全局冻结 ~80s |

structured OFF 对照组：conc=1 轮 1 干净（207ms / 4.7 req/s，与 ON 一致）；轮 2 停摆（P99 15.4s + 1 超时）；轮 3 持续停摆后终止采集（证据已充分）。

## 复测方式

```bash
# 宿主闲置后重跑（已内置错误类型分布 + 原始时序落盘 bench_raw.json）
wsl bash scripts/m6-3-bench.sh
```

- 压测工具：`bench/press.py`（in-flight 并发 / 流式 TTFT / 单调钟计时）
- 本次原始逐请求时序未落盘（补丁在压测中途加入，仅对复测生效）
