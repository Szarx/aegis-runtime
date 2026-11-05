# Policy Engine

状态：SPEC-009 已实现标准库版本的本地精确匹配策略。本地开发包 aegis-runtime-policy，不依赖 SDK、网络或数据库，未公开发布。

`src/aegis_policy/` 提供不可变 Rule / Policy / Decision；`tests/` 验证优先级、默认拒绝、严格输入和快照隔离。

首个实现供 Runtime 调用，输出 allow / deny、固定原因、策略版本和匹配规则；不直接执行工具。require_approval 留待后续，不在当前格式接受值中。

优先级：显式 deny → 显式 allow → 默认 deny，精确匹配 subject / tool / permission。同类匹配按规则 ID 排序取首个，效果不依赖规则顺序。

## 本地格式

```json
{
  "schema_version": "aegis.policy.v1",
  "revision": "demo-v1",
  "rules": [
    {"id":"allow-read","effect":"allow","subjects":["order-agent"],"tools":["lookup_order"],"permissions":["orders.read"]}
  ]
}
```

使用 Policy.from_dict 或 Policy.from_json 加载；后者也拒绝重复 JSON 键。根与规则未知字段、错误类型、重复成员/ID、超过 128 条规则或单列表超过 128 项均拒绝。三个匹配列表非空；空规则集有效且默认拒绝。标识为 ASCII 字母数字开头，后续允许字母数字和 ._:-，最长 128；不支持通配符、表达式或正则。

加载复制输入并冻结，原字典/列表修改不影响快照，直接构造也执行校验。策略加载错误抛固定 ValueError，不能回退成允许。Policy.evaluate 为纯函数；工具阻止和 ActionDenied 由 Runtime 执行。完整边界见 [SPEC-009](../specs/009-runtime-policy/spec.md)。

设计入口：[Architecture](../ARCHITECTURE.md)、[Phase 2](../ROADMAP.md)。

## 策略开发与验收：SPEC-022

SPEC-023进一步提供`python -m aegis_policy compare BEFORE AFTER --cases CASES`，报告规则结构与用例决策变化。配置变化或基准预期不符返回review_required/1，输入输出错误2；不会安装候选策略。见[变更评估指南](../docs/policy-comparison.md)及[023验收](../specs/023-policy-comparison/tasks.md)。

新增标准库workbench模块及`python -m aegis_policy check/explain`，支持严格文件加载、单次决策解释、批量用例验收、有限规则覆盖及独占JSON报告。规范指纹仅用于本地比较，不替代审批摘要或认证；旧Policy/Rule/Decision与求值语义保持。操作和退出码见[工作台指南](../docs/policy-workbench.md)，可运行[验收后接入Runtime示例](../examples/policy-workbench/README.md)，证据见[022任务](../specs/022-policy-workbench/tasks.md)。

SPEC-045：显式Policy v2支持require_approval，优先级deny>require_approval>allow；原v1规则与摘要不变。case/check/explain/compare/replay同步扩展，见[策略审批](../docs/policy-approval.md)。
