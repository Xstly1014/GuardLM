#!/bin/bash
# M1 收尾全链路：人审结论应用 -> promote -> 合并 -> 去重 -> 切分 -> 增强 -> 组装 -> 隔离校验
set -e
cd /mnt/e/workspace_work/GuardLM
source /root/guardlm-venv/bin/activate

echo "===== [1/8] 应用人审结论（#24 淘汰 / #45 改标） ====="
python scripts/m1/m1-apply-review.py

echo "===== [2/8] promote 合成样本打标合入 ====="
python scripts/common/promote.py --in data/interim/synth.raw.jsonl \
  --exclude-file review/m1_synth_exclude.txt \
  --out data/interim/synth.unified.jsonl

echo "===== [3/8] 合并三源 + 合成 ====="
python scripts/m1/m1-merge-pool.py

echo "===== [4/8] MinHash 去重 ====="
python scripts/common/dedup.py --in data/interim/all.unified.jsonl \
  --out data/interim/dedup.unified.jsonl \
  --jaccard 0.9 --report reports/m1_dedup.md

echo "===== [5/8] 三档评测集切分（先切评测再增强铁律） ====="
python scripts/common/split_eval.py --pool data/interim/dedup.unified.jsonl

echo "===== [6/8] T2 评测母本专属变体 ====="
python scripts/m1/m1-augment-eval.py

echo "===== [7/8] 训练池五件套增强 ====="
python scripts/common/augment.py \
  --in data/interim/train_pool.jsonl \
  --out data/interim/train_aug.jsonl \
  --modes pinyin,homophone,emoji,split,fan \
  --ratio 0.5 --none-ratio 0.07

echo "===== [8/8] 最终组装 + 隔离校验 ====="
python scripts/m1/m1_assemble.py --risk 3000 --ratio 3 --aug-pair-rate 0.5 --n-dpo 2000
python scripts/common/leak_check.py --train data/sft/train.jsonl data/rl/train_pref.jsonl \
  --eval data/eval/ --jaccard 0.6 --report reports/m1_leak.md

echo "===== 全链路完成 ====="
