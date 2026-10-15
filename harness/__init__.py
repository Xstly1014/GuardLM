# -*- coding: utf-8 -*-
"""GuardLM 评测 Harness v1（M2-T1）。

模块划分:
  backend  推理后端（M2 用 transformers 批量 generate，M6 换 vLLM）
  parse    JSON 五步容错解析（剥代码块→截取大括号→json.loads→json_repair→pydantic）
  metrics  混淆矩阵 + 总体/分档 P/R/F1/FPR + 对抗档分扰动子表
  report   Markdown 报告渲染
  run      CLI 入口

设计原则（M2 手册）:
  - 格式错误率本身就是被测指标，不做第 5 层自修复循环、第 6 层约束解码（留给 M6）
  - 推理后端与指标计算解耦：换后端不动指标
"""
