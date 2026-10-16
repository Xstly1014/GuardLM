#!/usr/bin/env bash
# M6-5: 校验 guardlm-awq 与 guardlm-final tokenizer 一致性（掉点对比前提）
set -u
for d in /root/models/guardlm-final /root/models/guardlm-awq; do
  echo "== $d =="
  ls -la "$d" | awk '{print $5, $9}'
done
echo "== tokenizer.json md5 =="
md5sum /root/models/guardlm-final/tokenizer.json /root/models/guardlm-awq/tokenizer.json
echo "== 关键配置 md5 =="
md5sum /root/models/guardlm-final/tokenizer_config.json /root/models/guardlm-awq/tokenizer_config.json 2>/dev/null
md5sum /root/models/guardlm-final/generation_config.json /root/models/guardlm-awq/generation_config.json 2>/dev/null
