# SPEC-026：统一接入中的人工审核与单次恢复

2026-10-25，已验证。完整场景：版本化配置声明敏感工具→宿主显式绑定审核客户端和参数披露→prepare暂停返回动作ID→独立reviewer核对完整参数→重新构造宿主resume一次→查询审批和治理事件。覆盖同步/异步、分进程、拒绝/未批准、失败与未知，复用011/012原协议。

新增aegis.application.v2，根与遥测字段沿用v1，工具必须显式提供name/permission/execution/tool_revision。execution=direct时revision为null；reviewed时须合法revision。v1严格形状和默认direct行为不变，旧加载器拒绝v2。程序化ApplicationConfig新增默认schema_version=v1，v1不允许reviewed绑定。

app.tool拒绝reviewed配置，app.reviewed_tool拒绝direct/未知/重复配置；同名不能混绑。reviewed入口必须disclose_arguments=True，复用ReviewedTool/AsyncReviewedTool，借入宿主提供的准确类型客户端（sync/async由函数类型决定）；不读取审核凭证、不构造或关闭借用客户端。权限/策略/subject/工具版本来自不可变Application配置。

返回句柄仅有prepare/resume，不是可直接调用的工具函数。方法整体持有Application调用租约，含网络与await，未活动/关闭后失败；async取消释放租约但不重领或补偿。SDK生命周期仍只由Application管理，async客户端由宿主async with管理且原循环关闭。没有自动等待/轮询/运行工具的后台任务。

inspect/status对v2返回显式v2报告，列execution、tool_revision和requires_review，局部Policy allow不代表已批准。v1报告形状保持；只读检查不探测审批角色或服务，不证明审批配置有效。完整参数进入原审批服务需调用方明确披露，原HMAC/策略摘要/tool_revision绑定、永久消费claim、unknown不重试、旧010不能执行等全部保留。

可运行宿主示例支持prepare/resume两个独立进程及sync/async，使用固定合成参数和本地业务计数文件，终端只输出动作/状态/确认，不回显参数、凭证或业务返回。审核仍通过现有Dashboard/独立reviewer HTTP角色；示例不自动批准，业务失败/取消可能已有副作用。

AC2601：v1兼容、v2严格与不能降级、检查/诊断说明、显式披露/客户端类型和绑定。
AC2602：prepare/resume资源租约、未批准/策略拒绝/篡改/重复零执行、取消/失败/未知边界及借用客户端所有权。
AC2603：真实HTTP/PG+独立宿主进程、人工角色模拟审核、sync/async成功/拒绝/重复/参数变更、OTLP治理事件与完整参数隐私边界。
AC2604：独立Runtime安装/旧入口回归、完整操作指南/示例、机器证据和环境清理，无真实LLM或远端发布。
