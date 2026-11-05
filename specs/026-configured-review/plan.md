# SPEC-026 方案

ToolBinding追加显式execution/version，ApplicationConfig追加默认v1版本，loader按版本严格分支。原app.tool仅direct；新增lazy导入的reviewed绑定工厂，共用注册表并复用已有ReviewedTool/AsyncReviewedTool，外层prepare/resume租约不改变原函数签名、参数绑定或执行协议。

客户端由可信宿主显式构造并管理，避免同步Application关闭异步HTTP资源。新配置不携带审批凭证，完整披露仍需每次绑定显式开启。inspect只展示模式和本地Policy决策，不认证审核。

示例分进程prepare/resume，固定合成参数，独立reviewer真实HTTP作出决定，验证拒绝/过期/篡改/单次消费及未知。无服务API/SQL/UI变化；新Runtime wheel与旧v1/原审批全回归。
