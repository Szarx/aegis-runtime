# SPEC-020 方案

Collector新查询从现有spans JSONB字段派生白名单，SQL绑定所有筛选值、仅静态字段名。独立路由模块注册，沿用统一Trace认证；新路径不接入审批凭证。无迁移，保留既有事实存储。

Vue独立SecurityEvents组件复用QueryChannel的取消/限时机制，扩展允许的只读路径；lossless解析单独校验事件形状。App路由复用Trace会话认证，页面卸载清空组件数据并取消请求。测试分协议、PG、domain/channel/SSR、实际浏览器；实际seed通过官方OTLP而非直接写SQL生成事件。
