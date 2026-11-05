# SPEC-010 任务

状态：已验证。2026-10-18 完成自动化、构建和浏览器；2026-10-20 完成服务停止/重启后的持久化复核与清理。

- [x] T1001：冻结绑定、独立权限、状态与重试，不提前执行工具。
- [x] T1002：Runtime 准备客户端与本地参数/策略摘要。
- [x] T1003：迁移3、审批存储/路由、服务端时效与并发决定。
- [x] T1004：Dashboard 独立凭证、列表和记录决定。
- [x] T1005：纯函数/客户端/角色/真实PG/旧能力回归与浏览器验收。
- [x] T1006：打包、构建、OpenAPI、文档与安全边界证据。

## 验收结果

当前独立测试方法：Policy 5、Runtime 14、SDK 59、Collector 协议/API 22、真实 PostgreSQL 19、Onboarding 8，共127 Python；前端31，总计158，新增21。2026-10-18 实际执行，数据库无跳过；CLI、浏览器和打包不重复计入方法数。

| AC | 证据 |
| --- | --- |
| 1001 | 本地规范化、JSON 类型/大小/循环/深度边界，参数与密钥/策略变化改变摘要；原输入不改、原参数不发送 |
| 1002 | producer/reviewer/Trace 独立认证，默认关闭、部分/重复配置失败；严格字段/类型、固定错误、含无 Content-Length 的16KiB限制 |
| 1003 | 真实PG schema2→3保留旧Span；请求绑定幂等/冲突，重试不续期；行锁保证相反决定仅一个胜出，同决定保留首次时间/身份；过期状态与决定限制 |
| 1004 | 真正回环HTTP验证307不转发、超时不重试；坏/超大响应和绑定不符固定失败；批准记录不覆盖旧Runtime，受保护工具零执行 |
| 1005 | 三条合成请求与一条原生Trace，经实际ApprovalClient/HTTP/PG/页面；浏览器批准/拒绝、服务端reviewer、独立Trace认证、离开审批页清空凭证 |
| 1006 | 四个wheel本地构建/隔离目标安装，审批模块及迁移3随包分发；Windows/Docker构建、pip check、OpenAPI、文档链接与凭证模式检查 |

执行入口（仓库根目录，先安装锁定依赖与本地包）：

```text
python -m unittest discover -s runtime/tests -v
python -m unittest discover -s collector/tests -v
python -m unittest tests.integration.test_approvals tests.integration.test_collector tests.integration.test_llm tests.integration.test_graph_stream tests.integration.test_governance -v
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s policy-engine/tests -v
python -m unittest tests.contract.test_onboarding -v
```

PG测试需 AEGIS_TEST_DATABASE_URL 指向专用库，只创建/删除随机测试schema。前端使用 npm test / npm run build；Windows 子进程受限时以 node 直接运行 vitest / vue-tsc / vite 相同入口。

2026-10-20 恢复此前已停止的独立Compose项目后，复核三条原始绑定、创建/到期时间及决定均保留；实际客户端重复prepare未续期。数据库原始状态 pending / approved / rejected 各1；查询按服务器时间将前两者投影为 expired。原生Trace/Span各1，迁移为{1,2,3}。现有Runtime仍拒绝、工具执行0次。只清理 aegis-spec010-check 容器/网络，保留该数据库卷，未操作其他项目。

机器可读证据见 [validation.json](validation.json)。本机忽略目录 artifacts/approval-records 保存 prepared.json、http-query-after-rebuild.json、wheels.json 与 dashboard-decisions.jpg；当前接口快照见 [OpenAPI](contracts/openapi.json)，007为历史快照。33个官方来源ID、59个Python pin保持来源与哈希凭据，无新增第三方运行依赖、真实模型请求或公开发布。

## 明确未交付

批准记录不执行工具，不改变Policy/Runtime，不能作为未来直接调用业务函数的凭据。require_approval、可读关键参数审阅、单次领取/消费、执行确认与未知结果恢复属于后续spec。固定本地reviewer不是多用户登录；宿主与数据库管理员在信任边界内，未实现不可篡改审计或跨外部系统恰好一次执行。
