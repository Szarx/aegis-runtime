# 用真实事件评估候选策略

candidate.json允许demo-agent调用write_record/demo.write；它只供回放求值，不会自动装入Agent，也不调用工具。

按[安全事件示例](../security-events/README.md)上报默认25次尝试，再按[完整指南](../../docs/event-policy-replay.md)导出并执行：

```text
python scripts/replay_security.py artifacts/events-first --policy examples/event-policy-replay/candidate.json --output artifacts/replay-first.json
```

前提：本机已安装Policy包，输入目录是有效021导出包，输出父目录已存在且文件不存在。Collector可停止，无模型或审批凭证要求。示例返回review_required、退出1，摘要预期：

| 项 | 结果 |
| --- | --- |
| 事件 | 25，逐条保留Trace/Span/Action |
| widened | 5，原显式拒绝变候选允许 |
| narrowed | 0 |
| decision_changed | 0 |
| unchanged | 20，含缺身份仍拒绝和原允许记录 |
| revision_differences | 25，候选是新的revision |
| 原outcome | completed5、denied10、error5、cancelled5 |

允许后的error/cancelled没有被“修复”为成功，候选也未实际执行。把候选改为空规则集时，原15次允许会变为拒绝；真实集成测试已核对这条对照路径。只有历史事件不能证明未覆盖行为或相同revision配置一致，应联合[完整策略比较](../policy-comparison/README.md)审查。
