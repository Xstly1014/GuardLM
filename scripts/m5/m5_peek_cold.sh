#!/usr/bin/env bash
cd /mnt/e/workspace_work/GuardLM
/root/guardlm-venv/bin/python - <<'PYEOF'
import csv, sys
csv.field_size_limit(sys.maxsize)
for split in ['train', 'dev', 'test']:
    p = f'data/raw/cold/COLDataset/{split}.csv'
    try:
        with open(p, encoding='utf-8') as f:
            rows = list(csv.reader(f))
        print(split, 'rows:', len(rows)-1, 'header:', rows[0][:6])
        # 估算文本总量（找文本列）
        texts = [r for r in rows[1:] if len(r) >= 1]
        total = sum(len(r[0]) for r in texts)
        print(f'  文本列总字符: {total:,} (~{total/1048576:.1f}MB utf-8)')
    except Exception as e:
        print(split, 'ERR', e)
PYEOF
