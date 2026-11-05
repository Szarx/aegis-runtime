# ADR-0007：纯中断节点与宿主驱动执行

日期：2026-10-20。状态：采纳，对应 [SPEC-013](../../specs/013-langgraph-reviewed/spec.md)。

LangGraph恢复interrupt会重新进入节点；把prepare或副作用放在interrupt之前可能重复。使用纯gate.node，只暂停与校验签名收据；真实工具在宿主驱动的ReviewedTool中执行，复用已有单次claim。确认成功后显式继续图，业务value留在宿主。

精确checkpoint属于审阅绑定，但action键绑定稳定逻辑call，而非checkpoint：否则更新checkpoint可能为同一次未知副作用生成可重新审批的新动作。宿主负责稳定call/id/key和串行编辑thread；前/后snapshot检查不构成跨存储事务。未知结果保守放弃自动继续，不轮询/重试/租约释放。

使用已有LangGraph1.2.15，实际验证root checkpoint_map用于收据匹配；变更框架版本须重新验收，缺少该字段失败关闭。单个顶层interrupt先行，图异步/子图/多interrupt和持久checkpointer另行冻结，避免扩大恢复承诺。InMemorySaver只证明同进程宿主对象重建，不构成生产恢复证据。
