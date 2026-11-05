# SPEC-010 方案

- Runtime 的可选 approvals 模块使用标准库 JSON/HMAC/urllib，纯准备接口不引用业务函数；现有 Policy/Runtime 求值不变，不提前引入不完整的 require_approval。
- Collector 单体新增审批路由与 Pydantic 严格模型，独立 producer/reviewer 凭证；复用 Postgres 连接/事务，迁移 3 新表与数据库时钟/行锁。
- 审批配置默认关闭；Compose 新增可选环境变量，不创建公开默认审批凭证。显式配置时才启用，Trace 页面不获得额外权限。
- 独立 Dashboard 组件与有限 API 客户端，手动刷新/决定、不自动执行或轮询；token 仅组件内存、路由离开销毁。
- 先测纯绑定/故障与API角色，再做真实PG迁移/状态/并发；实际浏览器记录决定只针对合成准备票据，不批准真实业务动作。
- SDK/Policy/runtime治理映射仍沿用009；审批是数据库实体，不能把批准记录伪装成工具已完成。下一spec处理审阅上下文、单次领取、参数匹配及未知执行结果。
