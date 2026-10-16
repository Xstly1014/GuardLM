#!/bin/bash
# M6-2 验收 1: curl 约束解码测试（response_format json_schema + enable_thinking=False）
# 写入临时 json 文件避免引号转义问题
cat > /tmp/m6_test1.json <<'EOF'
{
  "model": "guardlm",
  "messages": [{"role": "user", "content": "你是内容安全审核员。判定以下文本的风险类别并输出 JSON。\n加V心 kefu99886 免费领福俐，先到先得"}],
  "max_tokens": 64,
  "temperature": 0.7,
  "top_p": 0.8,
  "chat_template_kwargs": {"enable_thinking": false},
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "verdict",
      "schema": {
        "type": "object",
        "properties": {
          "label": {"type": "string", "enum": ["insult","porn","ads","illegal","none"]},
          "risk": {"type": "number"},
          "reason": {"type": "string"}
        },
        "required": ["label","risk","reason"],
        "additionalProperties": false
      }
    }
  }
}
EOF
echo "=== 约束解码 ON ==="
curl -s http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d @/tmp/m6_test1.json | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['choices'][0]['message']['content']); print('finish:', r['choices'][0]['finish_reason'])"

echo "=== 无约束（对照组）==="
python3 - <<'PY'
import json
d = json.load(open('/tmp/m6_test1.json'))
d.pop('response_format')
json.dump(d, open('/tmp/m6_test2.json','w'), ensure_ascii=False)
PY
curl -s http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d @/tmp/m6_test2.json | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['choices'][0]['message']['content'])"
