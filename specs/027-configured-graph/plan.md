# SPEC-027 实现方案

先冻结契约，再按完整接入闭环开发和验收。

1. 在application追加不可变GraphBinding和v3严格分支，保留v1/v2输出。新增managed_graph延迟构造原同步/异步图驱动，节点和整个方法借用Application租约。
2. 新配置示例共用严格ticket/图装配，sync使用原SqliteSaver上下文，async使用原格式预验证及宿主aiosqlite上下文。状态读取不构造Application或审批客户端；模式与版本由配置和checkpoint共同核对。
3. Runtime契约覆盖真实图、状态/版本/参数、生命周期和故障；真实PG测试调用新进程，经独立reviewer角色决定，再读取事件/Trace并导出核验。复用既有服务和四迁移。
4. 新wheel全新离线venv先验证无图核心导入，再显式安装extra验证持久图。全回归后写回spec/tasks/validation及产品文档；专用Docker项目清理且保留卷。

不修改013–015图执行/审批核心，不新增策略DSL、分布式执行、并行中断或收据恢复协议。v3是新增显式格式，不改变旧配置含义。
