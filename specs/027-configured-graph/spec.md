# SPEC-027：配置驱动的持久化审批图完整接入

2026-10-25，已验证。场景：配置工具和图版本→同步或异步真实LangGraph暂停→本机SQLite保存精确checkpoint与ticket→独立reviewer审阅完整参数→新宿主进程领取并执行一次→确认后继续原图→查询审批、治理事件与Trace。无LLM依赖。

新增严格aegis.application.v3。根/遥测字段沿用旧版；每个工具必须显式name、permission、execution、tool_revision、graph。direct的revision和graph为null；reviewed有revision且graph为null；reviewed_graph有revision和graph={id,revision,node}合法标识。v1/v2形状、检查和状态报告保持；它们不接受reviewed_graph。v3检查/状态报告显式v3，不把Policy allow当作人工批准。

app.reviewed_graph_tool显式借入准确类型的ReviewedClient或AsyncReviewedClient（由函数类型选择），要求disclose_arguments=True。配置固定权限、主体、策略、工具/图版本与节点。同名不可重复或经app.tool/app.reviewed_tool降级。句柄只暴露node、prepare、resume，业务函数不可直接调用。node纯中断/收据验证；prepare/resume整体持有Application租约，包含网络、业务、checkpoint核对和图继续；关闭后所有入口失效。客户端、SQLite连接及图由宿主拥有，Application只管理自己的SDK。

复用013–015原协议、精确snapshot绑定、HMAC收据、单根单interrupt和本机SQLite格式。claim消费不可撤销；业务失败、取消、确认unknown不能重新执行。业务确认与checkpoint不构成共同事务；完成确认丢失或图继续失败可能需要人工对账，不自动重建收据、重开动作或补偿。异步在原循环/任务await；无自动审批/后台轮询/线程桥接。

示例支持start/status/resume独立进程，sync/async、合成成功/失败/取消。配置显式提供，ticket包含完整参数，状态目录属于可信宿主敏感数据；业务效果文件只记录计数。status仅本地checkpoint读取，不初始化SDK/审批客户端、不向服务请求，不证明服务端批准。start新建状态目录，resume不重新初始化/覆盖checkpoint。配置版本或ticket/snapshot变更失败关闭。终端不回显完整参数、凭证或业务返回。

AC2701：严格v3、旧版兼容、图元数据/检查/状态、无降级/重复/隐式披露、可选依赖延迟加载。

AC2702：真实同步/异步图暂停与恢复、整个生命周期租约、关闭后拒绝、参数/图版本/精确snapshot绑定、取消/失败/unknown零重复，宿主拥有借用资源。

AC2703：真实HTTP/PG、独立审核角色和sync/async分进程SQLite恢复；未批准/拒绝/篡改零执行、成功一次并继续、重复不增加、故障不继续；治理事件关联恢复Trace且不泄漏参数，可导出离线核验。

AC2704：全新核心安装与显式图extra安装、可运行操作文档、完整回归、机器证据和专用环境清理。既有服务API、迁移、依赖pins与UI不变；无真实模型或远端发布。
