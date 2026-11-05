# SPEC-011 任务

状态：已验证，2026-10-20。

- [x] T1101：冻结完整参数审阅、独立执行身份、新旧隔离与未知结果行为。
- [x] T1102：迁移4、原子新建/决定/单次领取/结果确认与角色路由。
- [x] T1103：同步ReviewedTool，签名/参数快照、保守时效和策略复核。
- [x] T1104：独立执行审批页面、完整参数和未知/最终状态。
- [x] T1105：单元/真实PG/HTTP/浏览器与旧能力兼容回归。
- [x] T1106：wheel、生产构建、OpenAPI、设计/接入文档与机器证据。

## 验收与证据

本增量实际通过Policy 5、Runtime 23、SDK 59、Collector协议/API 26、真实PostgreSQL 26、Onboarding 8，共147 Python；前端35，总计182个独立方法，新增24（Runtime9、API4、PG7、前端4）。子场景/CLI/浏览器/构建不重复计数，数据库无跳过。最后的输入边界修正重新运行9个相关Runtime方法；其余已通过且未受影响的方法不重复执行。

| AC | 实际结果 |
| --- | --- |
| 1101 | 显式披露/函数种类/签名/默认值/严格JSON边界，跨客户端与服务端摘要一致；独立参数快照阻止原容器变化，策略/版本/身份/参数绑定变化不得领取 |
| 1102 | 默认关闭及独立producer/reviewer/executor/Trace凭证、固定执行身份；未知字段/错误类型/审阅摘要/体大小拒绝，新旧协议无法互相升级或审核 |
| 1103 | 真实PG schema3→4保留旧准备记录，原生/LLM等旧迁移回归通过；并发创建幂等、4并发领取仅1成功，同claim也不可重领，完成幂等/相反冲突、过期/错误绑定/身份拒绝 |
| 1104 | 真实HTTP/CLI：成功工具1次、拒绝0次、部分失败1次、领取响应丢失0次；重复恢复没有额外副作用。成功返回原对象；业务异常身份保持；完成确认失败unknown不重试；观测钩子延迟后最终时效检查仍阻止函数 |
| 1105 | 浏览器完整默认值、工具版本、9223372036854775807精确显示；核对后批准/拒绝，完成/失败/claimed未知可见；新旧页面切换清空审核会话，旧列表仅1条准备记录，浏览器无执行凭证/执行按钮 |
| 1106 | 四个wheel构建/隔离目标安装，新增Runtime模块与迁移4随包分发；核心导入不加载可选框架或Collector。Windows/Vite/TypeScript与Docker生产构建、pip check、OpenAPI和文档/凭证扫描通过 |

主要执行入口（仓库根目录，安装锁定依赖与本地包）：

```text
python -m unittest discover -s runtime/tests -v
python -m unittest discover -s collector/tests -v
python -m unittest tests.integration.test_reviewed tests.integration.test_approvals tests.integration.test_collector tests.integration.test_llm tests.integration.test_graph_stream tests.integration.test_governance -v
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s policy-engine/tests -v
python -m unittest tests.contract.test_onboarding -v
```

PG需专用AEGIS_TEST_DATABASE_URL，测试创建/删除随机schema；前端npm test/npm run build，Windows受限时直接以node运行相同vitest/vue-tsc/vite入口。测试方法在本增量中分批执行，不声称一条命令完成所有验证。

独立Compose项目中存5条审批：4条新协议，执行状态available/claimed/completed/failed各1；旧准备记录1条。宿主合成事件文件正好2行（成功/部分失败）。重建及重启后，绑定、原创建/到期时间和领取/结果确认时间均保留；再次恢复全部被阻止，事件仍为2行。已过期审批状态与历史执行结果分别保留；没有自动释放未知动作。

本轮仅清理aegis-spec011-check容器/网络并保留数据库卷，未操作其他项目；临时浏览器页已关闭。机器证据见 [validation.json](validation.json)，当前 [OpenAPI](contracts/openapi.json)；010/007保留历史快照。忽略目录artifacts/reviewed-execution包含CLI、HTTP、wheel哈希及三张页面截图。零新增真实模型/外部业务系统请求，无公开发布/提交推送，无新增第三方运行依赖；33个官方来源ID、59个Python pin及两平台下载凭据保持核对。

## 未交付与边界

仅普通同步具名JSON工具；Policy DSL require_approval、异步取消和LangGraph checkpoint/interrupt恢复待独立spec。完整参数需宿主显式披露，不可放secret；旧010仍只存HMAC且绝不能执行。永久消费领取会保守放弃部分未开始动作，unknown与failed均不能重试业务。宿主/原函数/数据库管理员仍可信；不承诺进程隔离、生产多用户/租户、不可篡改审计、进程暂停后实时保证或外部系统恰好一次。
