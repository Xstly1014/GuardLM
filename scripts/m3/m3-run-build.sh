#!/usr/bin/env bash
# M3-1b: 组装偏好对（WSL2 偶发段错误 -> 自动重试）
cd /mnt/e/workspace_work/GuardLM
for i in 1 2 3 4 5; do
  python3 -u scripts/m3/m3_build_prefs.py --total 2000 --mirror 150 > logs/m3_build.log 2>&1
  rc=$?
  if [ $rc -eq 0 ]; then
    echo "OK on attempt $i (rc=$rc)"
    break
  fi
  echo "attempt $i failed rc=$rc, retrying..."
done
tail -30 logs/m3_build.log
