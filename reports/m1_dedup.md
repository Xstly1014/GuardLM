# M1 去重报告

- 输入: 122183 条
- 第 1 级精确去重: 移除 0 条（整行 md5 相同）
- 第 2 级 MinHash（num_perm=64, Jaccard≥0.9）: 移除 33 条
- 输出: 122150 条

## 重复来源归因（被移除侧）

| source | 移除条数 |
|---|---|
| cold | 26 |
| safety_prompts | 7 |

## 相似对样例（前 20 对，人工复核用）

- 保留 `cold:train:005390` ← 移除 `cold:train:005623` (source=cold)
- 保留 `cold:train:005390` ← 移除 `cold:train:006756` (source=cold)
- 保留 `cold:train:002471` ← 移除 `cold:train:009571` (source=cold)
- 保留 `cold:train:000155` ← 移除 `cold:train:011286` (source=cold)
- 保留 `cold:train:005027` ← 移除 `cold:train:011607` (source=cold)
- 保留 `cold:train:011553` ← 移除 `cold:train:015397` (source=cold)
- 保留 `cold:train:011553` ← 移除 `cold:train:015913` (source=cold)
- 保留 `cold:train:011553` ← 移除 `cold:train:016881` (source=cold)
- 保留 `cold:train:005495` ← 移除 `cold:train:018302` (source=cold)
- 保留 `cold:train:014079` ← 移除 `cold:train:019940` (source=cold)
- 保留 `cold:train:011553` ← 移除 `cold:train:020688` (source=cold)
- 保留 `cold:train:019539` ← 移除 `cold:train:020741` (source=cold)
- 保留 `cold:train:007548` ← 移除 `cold:train:020774` (source=cold)
- 保留 `cold:train:019316` ← 移除 `cold:train:022129` (source=cold)
- 保留 `cold:train:023285` ← 移除 `cold:train:023388` (source=cold)
- 保留 `cold:train:020274` ← 移除 `cold:train:023682` (source=cold)
- 保留 `cold:train:001345` ← 移除 `cold:train:023789` (source=cold)
- 保留 `cold:train:016664` ← 移除 `cold:train:025621` (source=cold)
- 保留 `cold:train:024295` ← 移除 `cold:dev:002016` (source=cold)
- 保留 `cold:train:021552` ← 移除 `cold:dev:002108` (source=cold)
