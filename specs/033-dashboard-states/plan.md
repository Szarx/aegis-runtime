# SPEC-033 方案

1. 本地AsyncViewState显示加载/错误，lazyView统一defineAsyncComponent配置；SSR测试验证成功/失败分支与异常不泄漏，不安装新库（Vue已包含server-renderer）。
2. App区分同条件刷新与新查询，补充页面更新时间和查询状态；审批统计在未载入时显示横线。
3. 只在忽略tmp中的验收服务注入延迟/503，不修改Collector生产接口；浏览器检查旧结果标记、服务失败和手动重试。生产bundle经032入口验收。
