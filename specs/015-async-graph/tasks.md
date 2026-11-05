# SPEC-015任务

状态：已验证，2026-10-22。

- [x] T1501：冻结异步图、连接所有权与取消边界。
- [x] T1502：异步图/原生SQLite配置及共享纯校验。
- [x] T1503：取消、deadline、资源和受影响回归。
- [x] T1504：真实HTTP/PG/SQLite与独立进程示例。
- [x] T1505：wheel/extra/文档/协议/来源与验收记录。

## 实际验收

本轮最终82个不同方法通过：Runtime65、真实HTTP/PG17，无跳过。新增11个Runtime和2个PG方法，共13；旧221中69重跑、152沿用，当前目录234（含沿用的35前端方法）。复跑、子场景与进程不重复计数；未修改/重建前端。

首次组合运行81/82通过，一个新集成方法的四个独立场景误用同一graph/thread/call，第二次prepare被稳定action绑定正确拒绝。测试改为独立thread ID后，仅重跑该方法通过，生产实现未因此改动。首次单独Runtime运行的父Span断言误用全局tracer，改用SDK observe后已在65项组合回归中通过。初始结果和针对性复跑分别保留，不冒称一次全绿。

最终复核补强游标清理：fetchall超时/取消后不再额外await排队的cursor.close，宿主关闭整个连接，避免清理延长配置期限。以真实原生SQLite慢第二行验证fetchall阶段的期限；夹具先ALTER TABLE会加载temp库而提前被拒绝，改用新连接后命中目标阶段并通过。受影响4项存储+2项真实PG/CLI再次回归，最终wheel重新构建/隔离安装；6项复跑不增加方法计数。

| AC | 实际结果 |
| --- | --- |
| 1501 | 惰性协程/发送前取消零请求；拒绝同步函数、历史配置与错误thread；真实异步StateGraph使用aget_state/ainvoke，禁止同步get_state仍成功。篡改参数或checkpoint在claim前拒绝；原同步13项图回归通过 |
| 1502 | claim/业务/确认、初始/领取后/确认后snapshot及图继续共多个取消边界保持原CancelledError对象；领取前0次、领取后最多1次业务，已消费动作不重领。慢checkpoint读取不能延长领取deadline；确认普通错误保留原value/unknown，后验变更blocked，图普通错误unknown，原业务异常身份保持 |
| 1503 | 官方AsyncSqliteSaver关闭重开读取精确原snapshot，异步完成可用同步格式读取；WAL/FULL、严格无pickle/共享serializer、借入连接未关闭。memory/其他格式/attached/事务/版本/缺列拒绝；排队原生SQL时超时或取消，宿主排空并关闭工作线程，无SQL撤销承诺 |
| 1504 | 真实HTTP/PG与native异步SQLite：新连接/图对象恢复、成功、已提交claim/complete响应取消、工具中取消；状态分别completed/claimed/claimed/completed，无重复业务。新CLI独立进程start/status/resume/status/再次resume共10次，成功与部分失败各5次，业务各1次 |
| 1504 上下文 | SDK observe父Span与受控工具保持父子关系，原返回对象保持，Span未记录合成私有参数/异常正文；旧实际OTLP/PG与014四方法47子进程回归通过 |
| 1505 | 四wheel重新构建/独立安装，全新venv核心无可选包但可导入新模块；离线extra锁定既有版本，真实原生异步图pause/重开，无Provider/Collector安装。OpenAPI精确等于011、四SQL与014逐字节一致。62-pin两平台缓存SHA256/原59历史收据、41来源、链接、凭证模式和pip check通过 |

执行入口（仓库根目录，安装锁定开发依赖和本地包）：

```text
python -m unittest discover -s runtime/tests -v
python -m unittest tests.integration.test_async_graph -v
python -m unittest tests.integration.test_reviewed tests.integration.test_async_reviewed tests.integration.test_graph_reviewed tests.integration.test_durable_graph -v
```

PG测试使用专用AEGIS_TEST_DATABASE_URL、随机schema和临时SQLite；Windows原生asyncio/回环测试在允许本机通信的进程执行。实际Python3.12.14，本轮没有Linux异步图场景或多Python版本测试。Linux Collector构建/健康沿用014，Dashboard构建/35方法沿用011，无服务端/SQL/UI改变。

## 证据与边界

[validation.json](validation.json)保存方法计数、取消/存储/进程与包证据。忽略目录artifacts/async-graph包含初始tests.log/initial-tests.json、最终tests.json、针对性rerun.log、post-review.json/log、四个真实HTTP场景、10个子进程PID/返回码、安装报告、四wheel哈希和Docker清理记录。最终6方法复跑又执行10次异步CLI，进程receipt保留最新成功批次，不把复跑次数算作额外场景。

仅清理aegis-spec015-check自己的容器/网络；临时schema为0，postgres_data卷保留，其他项目未动。未提交/推送或公开发布，本轮零真实LLM请求。

仅本机单宿主串行驱动一个root interrupt，沿用014格式1。宿主拥有aiosqlite线程，取消排队SQL后必须关闭排空；重复关闭取消仍由宿主负责。无跨库事务/强制SQL终止、生产多机协调、多interrupt/子图、跨版本迁移、completed收据重建或未知结果自动补偿。下一增量继续先冻结spec。
