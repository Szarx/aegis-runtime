# SPEC-001：Python SDK 基础追踪

- 创建日期：2026-10-13。
- 状态：行为契约已确定；实现与验收状态见 [tasks.md](tasks.md)。
- 对应路线：Phase 1A 的第一个 SDK 增量，不表示平台端到端 MVP 已完成。

## 用户场景

开发者有一个原生 Python Agent，希望通过初始化及少量装饰器，看到每次 Agent 和工具调用的父子关系、耗时与错误，并且保持原有返回值、异常和工具副作用。此增量先输出本地 Trace，验证公共 API 与标准上下文。

## 范围

实现 `init`、`observe`、`tool`、`flush`、`shutdown`，同步函数、普通 `async def`、嵌套与并发上下文，以及容量受限的本地 JSONL 批量导出。提供无需外部凭证的订单查询示例。

暂不实现 LLM Wrapper、框架适配、网络 Exporter、Collector、数据库、Dashboard、内容采集开关和策略执行。JSONL 是本地调试格式，不是 OTLP；后续通过独立 spec 引入标准 OTLP 传输。

## 公共 API

```python
import aegis
from aegis import observe, tool

sdk = aegis.init(service_name="order-service", output_path="artifacts/traces.jsonl")

@tool(permission="orders.read")
def lookup_order(order_id: str):
    return existing_store.lookup(order_id)

@observe(name="customer-agent")
def customer_agent(order_id: str):
    return lookup_order(order_id)

result = customer_agent("demo-order")
flushed = aegis.flush(timeout_millis=5000)
diagnostics = sdk.diagnostics()
stopped = aegis.shutdown(timeout_millis=5000)
```

`init` 返回 SDK 生命周期句柄。默认输出路径为 `artifacts/traces.jsonl`，相对路径基于应用工作目录。也可通过 `exporter` 注入标准 OTel `SpanExporter`，此时不能同时指定 `output_path`。

队列配置为 `max_queue_size=1024`、`max_export_batch_size=64`、`schedule_delay_millis=1000`；必须为正整数且批次不大于队列。`service_name`、显式 `name` 和 `permission` 是长度 1–128 的非空字符串。

装饰器支持 `@observe`、`@observe()`、`@observe(name=...)` 和对应的 `tool` 形态；默认名称为函数名。已识别的 generator / async generator 函数在装饰时明确拒绝，避免仅追踪生成器创建而声称追踪完整流式消费。

未初始化及关闭后，装饰函数直接按原逻辑执行。重复初始化一个仍运行的默认 SDK 抛出配置错误，需先关闭；初始化和关闭应在应用启动与停机边界调用。关闭不等待业务函数完成，应先 await / join 业务工作。

`flush` 与 `shutdown` 的超时参数为非负整数毫秒；返回 bool。超时或会话中发生过导出失败时返回 false。队列溢出单独通过诊断计数报告，调用者应同时检查诊断。flush 只承诺等待调用时已接收的完成 Span，不承诺等待正在运行的业务或强制终止阻塞的 Exporter。

## 行为要求与验收编号

| 编号 | 要求 | 验收方法 |
| --- | --- | --- |
| AC-01 | Agent / Tool 创建标准 OTel Span，同一调用链共用 Trace，工具父节点正确 | 同步成功、嵌套 Agent 和单独工具验证 |
| AC-02 | 支持异步及并发隔离，接续已有上游 OTel 上下文 | 并发任务与外部父 Span 验证 |
| AC-03 | 不改变返回对象、函数签名、异常对象或副作用次数 | 比较对象身份与工具计数；成功和异常各一次 |
| AC-04 | 原始参数、返回值、异常消息与堆栈不采集 | 注入合成秘密，检查完整序列化记录中不存在内容 |
| AC-05 | 错误及取消标记 ERROR，记录异常类型，重新抛出原异常 | 普通异常、取消、失败工具与父 Agent 验证 |
| AC-06 | 导出在后台，队列有上限，失败不重试业务 | 阻塞/抛错 Exporter、溢出和副作用计数验证 |
| AC-07 | flush / shutdown 返回时间有界，可诊断失败与丢弃 | 使用可控阻塞 Exporter 和有限超时验证 |
| AC-08 | 保留宿主全局 TracerProvider，配置隔离可重建 | 初始化前后身份比较、关闭后重建 |
| AC-09 | 本地格式与固定契约一致 | 解析 JSONL，校验标识、状态、资源、事件和版本 |
| AC-10 | 原生示例无需外部凭证，可以复现成功和失败 | 运行示例，校验 2 次 Run / 4 个 Span 与父子关系 |
| AC-11 | 禁用时直接执行；不支持的函数/错误配置明确报告 | 未初始化、关闭后、生成器和非法配置验证 |

## 标准与数据边界

使用 OpenTelemetry Python API / SDK **1.45.1**；GenAI 参考固定提交 `5293effb97f18ddb0602da884dadee6119d67679`。此次只映射 `invoke_agent` / `execute_tool` 及 Agent / Tool 名称，映射版本 `aegis.genai.v1`。GenAI 规范仍处于 Development，不能把此子集称为完整兼容。

SpanKind 使用 INTERNAL，成功保持标准 UNSET，失败为 ERROR。工具 `permission` 仅写入 `aegis.tool.permission`，不触发策略。SDK 自有 Provider 不安装为宿主全局 Provider。

本地输出的时间为 UTC Unix 纳秒整数，字段格式见 [JSONL 契约](contracts/span-jsonl.md)。身份、成本、Token、模型字段和可信审计均不在此增量中。

## 隐私与故障约束

默认只采集开发者配置的名称、权限、标准标识、时间和异常类型。名称与权限应来自静态配置，不填写用户输入。资源只包含服务名与已知 SDK 元数据，不自动复制环境变量。

Span 开始、上下文绑定或结束等观测操作出现普通异常时，业务仍执行一次；诊断增加 instrumentation failure。业务的 BaseException 包括取消仍传播。后台导出异常只增加通用失败计数，不输出异常消息或堆栈。

JSONL 采用追加写入，不提供跨进程原子性、事务持久性、去重、重试或防篡改保证。配置只读路径等故障应在诊断中呈现；shutdown 超时的后台线程可能稍后完成，不能强制杀死任意 Exporter。

## 验证与发布边界

目标支持 Python 3.11+，实际验证环境在任务清单记录。仅提供本地开发分发名 `aegis-runtime-sdk`，不声明 PyPI 名称占用或发布。许可证仍待选择，不自动发布或推送。

本 spec 完成后，下一增量设计 Collector 的 OTLP 传输与接收；不能将本地 JSONL 示例描述为已跑通数据库和 Dashboard。
