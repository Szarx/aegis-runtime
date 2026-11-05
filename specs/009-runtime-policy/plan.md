# SPEC-009 方案

- aegis_policy 标准库包：严格 JSON schema、frozen Rule/Policy/Decision、纯 evaluate。仅本地精确匹配，拒绝优先，缺配置失败关闭。
- aegis_runtime 进程内包依赖本地 Policy 和 SDK 分发，不依赖 FastAPI/数据库。实例持有 subject/策略；装饰器检查 generator/async generator 不支持，普通 sync/async 调用前统一决策。
- SDK 新增公共 governance 遥测上下文和独立 mapping；复用私有 Provider，只在观测层 fail-open。实际 authorization 永远在 Runtime，拒绝异常在上下文中记录但不能被观测错误吞掉。
- Collector 复用 JSONB，不改 SQL/查询 schema；新 mapping 严格配对。Dashboard 新增决策信息区和受控工具节点提示，不新增执行或审批入口。
- 示例使用可计数本地工具、两种身份/权限，不触发真实副作用/收费模型。自动化覆盖策略/Runtime/SDK/协议/真实数据库/UI领域，再用 Compose 和实际浏览器端到端验收。
- 原分发版本仍为 0.1.0.dev0，仅本地安装，许可证和公开发布不在范围。
