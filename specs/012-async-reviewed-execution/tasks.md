# SPEC-012 任务

状态：已验证，2026-10-20。

- [x] T1201：冻结async取消、确认和资源关闭语义，保留既有协议与同步行为。
- [x] T1202：公共纯准备逻辑、可选原生AsyncReviewedClient与AsyncReviewedTool。
- [x] T1203：确定性边界/取消/资源/并发上下文与同步回归。
- [x] T1204：真实HTTP/PG和无LLM的async示例验收。
- [x] T1205：可选extra/wheel/核心隔离、原OpenAPI/迁移不变与文档证据。

## 验收与计数

本增量实际执行Runtime33方法、真实HTTP/PostgreSQL相关9方法，共42方法通过，无数据库跳过。新增Runtime10、PG2共12方法。旧011的182方法中30方法本轮重跑，其余152方法沿用已完成证据；方法目录累计194，不声称本轮全部194重新执行。未改前端，沿用011的35方法及生产构建证据；CLI、安装、wheel和文档检查不重复计入方法数。

| AC | 实际结果 |
| --- | --- |
| 1201 | 专用async签名、显式披露、默认值/严格JSON快照与本地allow；未await或开始前取消均无请求/工具；领取后及函数前可取消/检查时效；旧同步测试全部通过 |
| 1202 | 错误状态/编码/重复键/过大响应、流持续返回但总期限到期、连接关闭/中断后补清理、跨循环拒绝；固定错误不泄露凭证/响应；缺可选依赖固定提示 |
| 1203 | prepare/claim中、领取后、函数中和成功/失败确认中取消；原CancelledError和业务异常对象保持；可能提交的claim永不重领；成功确认故障保留原value并标unknown |
| 1204 | 两Agent并发保留各自父Span与参数快照，上下文恢复、无遗留补偿任务；参数/异常正文不进入治理Span |
| 1205 | 原生HTTPX→实际Uvicorn回环HTTP→真实PG：并发领取仅一个函数开始，成功/失败/取消，服务端先提交再取消响应；重复恢复无新增副作用，OTLP入库/查询验证completed/error/cancelled |
| 1206 | 四本地wheel构建及独立目标安装；全新venv核心无HTTPX可导入，新async模块也不隐式加载HTTPX；离线追加extra后原生客户端关闭通过，无模型/框架/Collector包；OpenAPI与011精确一致，四份打包SQL与011 wheel逐字节相同 |

主要执行入口（根目录，已安装锁定依赖与本地包）：

```text
python -m unittest discover -s runtime/tests -v
python -m unittest tests.integration.test_async_reviewed tests.integration.test_reviewed -v
```

PG使用专用AEGIS_TEST_DATABASE_URL，测试创建/删除随机schema。本机Python3.12.14；Windows受限进程的asyncio检查可能阻塞，使用允许本机异步/回环通信的进程通过验证。wheel检查的首次受限异步关闭探针90秒超时，随后在允许该通信的进程完成剩余验证；未改变生产实现来规避取消检查。Python3.11+是最低API要求，未声称多版本执行验证。

## 实际合成Agent

[示例](../../examples/async-reviewed-execution/README.md)分进程prepare/resume，测试宿主通过独立reviewer凭证明确批准或拒绝，仅处理合成参数：成功追加1条、部分失败追加1条、函数中取消追加1条、拒绝0条。每个动作再次恢复均拒绝；重启HTTP宿主/重新打开数据库存储后，四条记录和原始时间保留，再次恢复仍无新增写入，总计3条。取消场景以工具进入信号触发，宿主拥有并等待任务结束，无时间猜测或后台补偿。临时schema已清理；数据库容器和卷处理见机器记录。

记录见 [validation.json](validation.json)。忽略目录artifacts/async-reviewed-execution保存CLI状态与计数、两阶段离线安装报告、四wheel哈希和合成事件。36官方来源ID、59第三方Python pin、两平台下载收据和npm锁保持核对；新来源为原创摘要/官方链接，不镜像第三方文档。服务端/前端无行为变化，未新增浏览器验收或冒称重建前端。零新增真实模型或外部业务请求，无提交/推送/公开发布。

## 边界与下一步

完整JSON参数主动披露，宿主身份/Policy/工具版本可信。取消网络不能撤销服务端事务，取消函数可能已有部分副作用；claimed未知、failed和completed均不能重试业务。关闭被取消/超时后可能需要在原循环再次aclose。库不接管工具内部自行创建任务或吞掉取消的行为。

LangGraph interrupt/checkpoint恢复、Policy DSL require_approval、生产多租户/身份、持久不可篡改审计和外部系统恰好一次仍未实现。下一增量先冻结图checkpoint与审批动作/参数/工具版本的绑定，继续先spec后代码。
