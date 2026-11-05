# 异步审批的官方依据

查阅日期：2026-10-20。以下为原创整理，未镜像第三方文档。

- [HTTPX Async Support](https://www.python-httpx.org/async/)：AsyncClient、异步上下文与响应关闭；本项目用原生异步传输，宿主显式管理客户端生命周期。
- [HTTPX Timeouts](https://www.python-httpx.org/advanced/timeouts/)：连接、读取、写入及连接池阶段分别受限；读取超时约束单段等待。因此本项目另加完整操作deadline，并限制累计响应大小。
- [Python3.11 asyncio任务](https://docs.python.org/3.11/library/asyncio-task.html)：取消、任务所有权和timeout机制。CancelledError原样传播，工具取消不等同于撤销外部事务。

4连接、5秒总期限、64KiB、永久消费claim、取消时不发送failed以及不做后台补偿均是Aegis SPEC-012的项目选择，不是这些来源规定的标准。实际验证使用锁定HTTPX0.28.1、Python3.12.14；支持Python3.11+的语法/API，未声称在每个Python版本执行测试。
