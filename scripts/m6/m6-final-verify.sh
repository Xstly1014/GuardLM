#!/usr/bin/env bash
# M6 收尾: 演示页最终验证（bf16 生产形态）
R=$(curl -s --max-time 90 http://localhost:7860/moderate \
  -H "Content-Type: application/json" \
  -d '{"text":"加我微信免费领福利"}')
echo "ads-example: $R"
R2=$(curl -s --max-time 90 http://localhost:7860/moderate \
  -H "Content-Type: application/json" \
  -d '{"text":"今天天气真好"}')
echo "none-example: $R2"
