# Aegis治理v2与兼容增量

此为Aegis自定义观测契约，不宣称第三方GenAI标准定义了人工审批事件。OTLP protobuf/HTTP与固定依赖保持。

v1治理原字段、效果、结果和校验保持。只有第三决策的记录使用aegis.mapping.version=aegis.governance.v2，operation=execute_tool、kind=INTERNAL；工具名称/权限/上报身份、policy revision/rule id、非零Action ID均必填。effect=require_approval且reason=explicit_require_approval，增加aegis.approval.phase：request或execute。

| phase | 允许outcome | status |
| --- | --- | --- |
| request | awaiting_approval | UNSET且无error.type |
| request | error / cancelled | ERROR且有error.type |
| execute | completed | UNSET且无error.type |
| execute | error / cancelled | ERROR且有error.type |

request不执行工具，可因审批服务错误/取消结束；execute仅在原claim与本地绑定校验通过后产生。除固定exception.type外无异常内容。参数/模型输入输出/凭证不进入Span。JSONL新映射为aegis.span.v5，原span v1-v4保持；SDK及Collector白名单只为v2保留phase。

安全事件API既有字段不变，effect/outcome枚举分别追加require_approval/awaiting_approval，按同一Action可查多个请求与执行Span。phase在Trace属性中查看。API路径版本仍v1，旧二元客户端可能拒绝展示第三种值；应配套升级Collector/Dashboard/导出器，不能声称旧前端兼容新记录。原v1记录继续可读。当前OpenAPI为本目录[快照](openapi.json)，020与011原快照保留；测试证明除上述枚举追加外，020字段/路径未变。JSONB存储复用原四迁移，不能据此承诺新增查询的生产规模性能。

审批claim/complete本体和永久消费语义保持；policy_digest仍绑定完整策略，v1摘要字节不变，v2摘要包括policy schema。策略入口的审批record不绑定可变化的请求Trace/Span，以Action ID关联事件，允许宿主用预存action_id显式重准备；这只恢复准备结果，不重执行业务。底层可选显式Trace绑定由调用方保存原ID并在恢复时复用。审批记录决定当前执行资格，历史awaiting_approval事件只是请求时快照。
