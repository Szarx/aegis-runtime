# 策略变更审查示例

before.json是基准，candidate.json是待审查候选，cases.json的8项预期只描述基准。三个文件均为声明式JSON，不执行工具或调用LLM。

```text
python -m pip install --no-build-isolation --no-deps -e ./policy-engine
python -m aegis_policy check examples/policy-comparison/before.json --cases examples/policy-comparison/cases.json
python -m aegis_policy compare examples/policy-comparison/before.json examples/policy-comparison/candidate.json --cases examples/policy-comparison/cases.json
```

预期compare返回review_required、退出1；比较before与before则返回unchanged、退出0。无效文件或已存在输出返回2。保存报告、CI用法及上限见[使用指南](../../docs/policy-comparison.md)。

| 变化 | 结果 |
| --- | --- |
| 删除deny-blocked、allow-read新增unknown身份 | blocked和unknown从拒绝变允许，widened=2 |
| allow-admin的effect改为deny | admin的archive从允许变拒绝，narrowed=1 |
| 新增deny-write | write请求仍拒绝，原因从no_match变explicit_deny，decision_changed=1 |
| read、未知工具、缺身份、缺权限 | unchanged=4 |
| 新增allow-future但用例未触及 | 仍列为新增规则和未选中覆盖，要求审查 |

结构报告为新增2、删除1、修改2，modified_details分别指出effect和subjects字段。规则ID只是标识，实际效果由effect决定；不要根据名字推断权限。

自动化验收把相同8个输入分别交给真实同步/异步Runtime：每种模式基准进入工具2次、候选3次，共32次尝试/10次业务函数进入；每次Span的effect/reason/rule_id与比较报告一致。测试工具仅固定返回值和内存计数，比较命令自身不会执行它们。

报告不提供全空间等价证明、生产完整性或部署授权。候选只有经过项目正常审查、由宿主显式选择后才可能生效；比较命令不改策略文件、运行中对象或既有审批。
