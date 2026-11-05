# SPEC-015方案

提取013的纯snapshot校验，异步类复用请求、action和收据规则；AsyncReviewedTool增加私有异步调用扩展点，图子类在await snapshot后核对deadline。取消遵循012，不额外补偿。

不在此增量实现新的异步连接工厂。宿主以标准aiosqlite上下文管理连接，配置函数仅在异步SQL中验证已有014文件，保留严格serializer和is_setup以禁止自动迁移。连接排队/关闭责任明确，避免用同步文件工厂阻塞运行中的事件循环。

先确定性取消和真实异步图单测，再真实HTTP/PG/SQLite和独立进程示例；按受影响范围回归，避免把子场景/子进程重复计数。62-pin不增版本，完成可选wheel和文档证据。
