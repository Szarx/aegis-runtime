# SPEC-014任务

状态：已验证，2026-10-22。

- [x] T1401：冻结本机SQLite、独立进程、未知动作和依赖边界。
- [x] T1402：可选官方持久checkpointer工厂、严格serializer与sync durability。
- [x] T1403：存储边界及受影响Runtime回归。
- [x] T1404：真实子进程/SQLite/HTTP/PG退出边界和分命令合成Agent。
- [x] T1405：62-pin来源/两平台收据、wheel隔离、文档/机器证据与清理。

## 验收与计数

本轮实际Runtime54、相关HTTP/PG13（新进程4+原图2+原同步审批7），共67个独立方法通过，PG无跳过。新增Runtime8、进程/PG4共12；旧209中55重跑、154沿用，目录累计221。子场景、47次独立子进程调用、构建、安装和复跑不累加方法数。前端未改，35项前端及构建沿用011，不声称本轮重跑。

| AC | 实际结果 |
| --- | --- |
| 1401 | 缺文件不创建、新建不覆盖、Unicode/空格/百分号路径、WAL/FULL、上下文关闭与原异常；不兼容marker/依赖/缺表列、损坏/其他SQLite库拒绝，锁等待有界；模拟只读I/O错误固定输出 |
| 1401 serde | 禁pickle且没有调用pickle.loads；构造自定义msgpack类型时无任意import，按官方实现退化为普通字典；官方Interrupt可持久化读取 |
| 1402 | 真正独立start进程退出后，status读原checkpoint、resume用新gate/图执行一次，另一个status读完成标记；重复恢复无新增事件，原同步/异步/图54方法及9个旧PG方法通过 |
| 1403 | 测试worker实际os._exit70..74：暂停已保存、claim已提交、写入已fsync、completed已提交、图sync写入后退出；后续进程均不重放工具，ticket/action保持，消费记录不释放 |
| 1404 | status删除审批凭证/key后仍成功、无业务；pending/rejected/expired、篡改参数/工具版本/marker、缺DB、重复键和过大ticket均零新增副作用。部分业务失败1事件，failed后再次恢复0新增；JSONL无参数/异常正文或凭证 |
| 1405 | 四wheel构建/独立目标安装，核心无SQLite extra可导入且缺依赖不创建文件；离线extra无Provider/Collector包，官方SQLite+真实图关闭重开通过。OpenAPI精确等于011，四份打包SQL与013逐字节相同 |

执行入口（根目录、锁定开发依赖及本地包）：

```text
python -m unittest discover -s runtime/tests -v
python -m unittest tests.integration.test_durable_graph -v
python -m unittest tests.integration.test_graph_reviewed tests.integration.test_reviewed -v
```

进程测试使用专用AEGIS_TEST_DATABASE_URL、随机PG schema和临时SQLite目录，测试后删除；每次调用真实Popen后等待退出。47次进程分布为正常跨进程流程5次、五个硬退出边界20次、部分失败4次、九类拒绝场景18次。最新成功运行四个方法均有passed证据，未将初次失败/复跑重复统计。

首次测试辅助代码用sqlite3连接上下文只结束事务、未关闭核对连接，Windows临时目录清理失败；改为closing后8项通过。首次进程测试辅助读取UTF-8 ticket时沿用Windows默认GBK，显式编码后4项全部通过；生产工厂/CLI本来就关闭连接/二进制读JSON，未通过改生产行为掩盖测试。Windows异步/回环测试在允许本机通信的进程执行。

## 退出边界结果

| phase | os._exit码 | 本次合成事件 | 结束后审批执行态 | 后续重复新增 |
| --- | --- | --- | --- | --- |
| pause | 70 | 批准后新进程恢复1 | completed，图完成 | 0 |
| claim | 71 | 0 | claimed，图暂停 | 0 |
| write | 72 | 1 | claimed，图暂停 | 0 |
| complete | 73 | 1 | completed，图暂停 | 0 |
| graph | 74 | 1 | completed，图完成 | 0 |

这是真实进程退出，不是断电测试。故障开关只存在tests/fixtures/durable_worker.py；生产 [示例](../../examples/durable-graph/README.md)无故障参数，支持start/status/resume。

## 交付与证据

[validation.json](validation.json)记录67方法、继承范围和包/容器证据。忽略目录artifacts/durable-graph保存4方法/47子进程的phase/PID/返回码/计数、离线安装报告、wheel哈希和Docker健康/清理记录。临时schema/状态已清理，不保存用户业务数据。

新增官方SQLite3.1.2、aiosqlite0.22.1、sqlite-vec0.1.9，仅可选extra；原59版本保持、当前62 pins，Windows/Linux官方wheel下载SHA256与新收据核对，006历史收据保留。41来源ID与文档链接核对。Linux Collector以62包离线构建、健康启动和原四迁移readiness通过；未声称在Linux重复执行47个Windows进程场景。四wheel为本地开发包，无公开分发/提交/推送，零LLM或外部业务请求。

仅清理aegis-spec014-check容器/网络并保留postgres_data卷，不操作其他项目。未更新前端/浏览器验收。实际Python3.12.14，最低3.11为API范围，不声称多Python版本测试。

## 边界

只验收本机、同步、单个宿主串行驱动同一thread；文件需宿主保护并支持示例的硬链接提交。marker不是防篡改/回滚审计，WAL/FULL不构成断电或硬件故障证明。其他图节点、原函数、key/身份与两个存储仍可信。

生产PostgresSaver、多机/并发调度、异步图/子图/多interrupt、跨版本迁移、completed收据重建与跨系统恰好一次均未交付；已消费动作不能因图暂停而重试。后续先维护对应spec，再扩展。
