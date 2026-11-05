# SPEC-001 实现方案

## 文件与依赖

- `sdk/python/pyproject.toml`：本地开发包、Python 3.11+、OTel 1.45.1。
- `sdk/python/src/aegis/`：生命周期、装饰器、上下文与导出模块。
- `sdk/python/tests/`：标准库 unittest，按 AC 编号验证行为。
- `examples/native-python/agent.py`：合成订单数据，成功与失败 Run。
- `requirements-dev.lock`：本次实际验证使用的完整依赖版本。

不引入具体 Agent 框架、服务端或前端依赖，保持这一增量可单独运行。

## 技术取舍

1. 使用 OTel 创建标识和上下文，而不是手写 Trace 标准；私有 Provider 仍接续当前 OTel 上下文。
2. 装饰器只包围一次函数执行。同步与异步入口共享上下文管理器，保留 `functools.wraps`。
3. 关闭 OTel 自动异常内容记录，仅记录异常类型和 ERROR，防止异常消息泄漏参数或凭证。
4. 实现一个小型 OTel `SpanProcessor`：受限 FIFO、单个后台线程、明确的等待截止时间与计数。基于公开接口实现，不读取 SDK 私有队列。
5. 单独实现标准 `SpanExporter` 的 JSONL 后端。后台进行文件写入，业务线程不接触文件 I/O。
6. flush 捕获当前已提交序号，等待该序号完成；失败是可见状态。shutdown 关闭入队并有界等待后台退出。
7. 生命周期不依赖隐式全局 OTel 初始化，不自动读取未知资源属性；结束业务后由调用者显式 flush / shutdown。

采用自有队列适配层，是为了在 SPEC-001 中明确验证超时、队列丢弃与导出诊断；仍使用 OTel 的 Span / Context / Exporter 公共接口。技术参考见 [遥测资料笔记](../../resources/notes/telemetry.md)。

## 验证顺序

契约与装饰器测试 → 并发/异常/隐私 → 故障与超时 → 安装检查 → 原生示例 → 文档状态更新。没有通过的项目保持未完成，完整端到端 MVP 仍在 ROADMAP 中待实现。
