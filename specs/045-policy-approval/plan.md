# SPEC-045 方案

1. Policy版本字段保持v1默认，Rule构造允许第三效果但Policy v1拒绝；同步扩展工作台/比较/回放。
2. SDK治理v2及Collector严校验/安全投影；原v1原样接受，现有JSONB存储不新增SQL迁移。
3. Reviewed核心增加可选Trace绑定与共用执行span；保留旧公共默认。新PolicyTool只选择分支，所有审批执行交回原claim/complete；票据在claim前做严格重建核验。Application v4显式装配及会话租约保护。
4. 原生/StateGraph示例显式request/resume驱动，独立人工决定；测试完整失败矩阵、真实平台、导出/回放和安装。最后才归档通过证据。
