# 实施方案

复用 SpanProcessor 的开始/结束回调和现有诊断计数。增加可选独立健康线程与 Collector 有界快照接口。前端以独立页面读取健康数据，并链接现有 Trace。最后完成 SDK、HTTP、前端和完整回归。
