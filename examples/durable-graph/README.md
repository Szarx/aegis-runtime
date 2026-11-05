# 独立进程的持久图示例

真实LangGraph、官方SqliteSaver、本机文件与独立start/status/resume进程，无LLM或外部业务调用。工具只向指定state目录的tool-calls.jsonl追加并fsync合成记录。先按 [持久图接入](../../docs/durable-graph.md) 安装可选extra、启动现有Collector/PostgreSQL/Dashboard，并配置producer/executor及至少32字节hex的稳定AEGIS_APPROVAL_BINDING_KEY。

在仓库根目录明确建立父目录，选择一个从未使用过的运行目录：

```powershell
New-Item -ItemType Directory -Force artifacts/durable-graph
python examples/durable-graph/agent.py start --state artifacts/durable-graph/run-001
```

start完成后进程退出，工具零执行。保留checkpoint.sqlite3、可能存在的-wal/-shm文件及ticket.json；不要复制活动数据库的单个主文件作为备份。数据均为本机可信文件，含完整实参，目录由宿主保护；凭证/key不写入这些文件。

独立查询暂停状态（不需要审批凭证，不访问审批服务、不执行工具）：

```text
python examples/durable-graph/agent.py status --state artifacts/durable-graph/run-001
```

在Dashboard“执行审批”核对action_id、graph_binding、完整arguments后批准，再用新进程显式恢复：

```text
python examples/durable-graph/agent.py resume --state artifacts/durable-graph/run-001
python examples/durable-graph/agent.py status --state artifacts/durable-graph/run-001
```

成功只追加1条，status显示完成；再次resume返回码1且不新增记录。`--endpoint`可指定实际回环HTTP origin，start/resume须一致；所有进程的key、身份、策略和工具版本须保持。默认TTL600秒，不会因进程重启续期。新终端需从宿主原来的秘密配置重新提供同一key，不能生成替代key。

start加`--fail`演示先追加1条再业务失败，resume返回码2，审批failed且图保持暂停；重复恢复仍拒绝。返回码3表示工具已返回但图继续未知/被阻止，不能重试工具。初始未批准、拒绝、到期、缺失/损坏状态均返回码1，无新增副作用。

start拒绝已有目录；状态丢失不能通过重新start同一业务意图补救。保存ticket时使用同目录硬链接原子发布，需要支持该操作的本机文件系统；本轮实际验证成功。退出发生在领取后或确认后时，即使图仍暂停也不能重新执行；本例不重建已完成收据。硬退出注入只在测试worker中，生产CLI没有故障开关。
