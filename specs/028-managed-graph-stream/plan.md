# SPEC-028 实现方案

1. Application.graph延迟导入managed_agent_graph。借用SDK observe_graph，限定四种执行方法与with_config；原SDK源码和配置版本保持。
2. 同步/异步流代理持有Application租约，复用SDK的Span/context生命周期；操作锁拒绝并发消费，async记录原循环。EOF/成功清理精确归还，清理失败禁止拉取并保留已取得租约，原异常优先。
3. 独立业务图接收宿主注入的模型client和工具装配函数；真实StateGraph/ToolNode+两轮官方SDK合成transport。对照允许/拒绝、完整/提前关闭/业务失败、同步/异步，终端仅计数/状态。
4. Runtime真实图契约、CLI矩阵、HTTP/PG聚合和导出、全新wheel核心/extra安装，再完整回归和文档证据。专用Docker项目不影响原服务。

不托管任意Python generator、不代理任意graph方法、不实现事件投影/审批流自动恢复或LLM自动发现，不引入新依赖pins。
