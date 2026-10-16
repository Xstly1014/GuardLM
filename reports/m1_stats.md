# M1 数据分布统计

| source | total | insult | porn | ads | illegal | none |
|---|---|---|---|---|---|---|
| cold | 31692 | 15776 | 0 | 0 | 0 | 15916 |
| sp | 89997 | 20000 | 34 | 0 | 26372 | 43591 |
| **合计** | 121689 | none 占比 48.9% |

## cold（31692 条）

| label | n | pct |
|---|---|---|
| insult | 15776 | 49.8% |
| none | 15916 | 50.2% |

- 长度: min=7 p25=23 median=41 p95=110 max=192
- origin_label 明细: off=1;topic=race=6902, off=0;topic=race=6358, off=0;topic=region=5517, off=1;topic=region=4779, off=1;topic=gender=4095, off=0;topic=gender=4041

## sp（89997 条）

| label | n | pct |
|---|---|---|
| insult | 20000 | 22.2% |
| porn | 34 | 0.0% |
| illegal | 26372 | 29.3% |
| none | 43591 | 48.4% |

- 长度: min=9 p25=25 median=33 p95=65 max=189
- origin_label 明细: Unfairness_And_Discrimination=10000, Crimes_And_Illegal_Activities=10000, Insult=10000, Physical_Harm/safe_tip=9988, Mental_Health/safe_help=9793, Privacy_And_Property/safe_help=9033, Reverse_Exposure=5000, Prompt_Leaking=5000, Unsafe_Instruction_Topic=5000, Inquiry_With_Unsafe_Opinion=5000, Goal_Hijacking=4999, Role_Play/benign=4777, Privacy_And_Property/snoop=966, Mental_Health/self_harm=206, Role_Play/extreme=189, Role_Play/adult=34, Physical_Harm/violence=12
