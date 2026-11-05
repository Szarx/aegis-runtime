# 本机持久checkpoint与进程恢复

SPEC-014将 [013的单个同步图中断](langgraph-reviewed.md) 延伸到独立Python进程，使用官方SqliteSaver和本机SQLite文件。审批仍由现有Collector/PostgreSQL协调，服务无LLM依赖，协议/四迁移/Dashboard不变。本轮不覆盖多机、多进程同时驱动、异步/子图/多个interrupt或生产PostgresSaver。

## 可选安装和工厂

```text
python -m pip install -e ./sdk/python -e ./policy-engine -e "./runtime[reviewed-langgraph-sqlite]"
```

extra固定LangGraph1.2.15、checkpoint4.3.0、checkpoint-sqlite3.1.2、aiosqlite0.22.1、sqlite-vec0.1.9；已有59版本保持，开发基线62。旧reviewed-langgraph extra不强制安装SQLite。工厂模块导入仅标准库，实际构造才要求可选包；不主动加载SQLite向量扩展。

```python
from aegis_runtime.durable_graph import open_reviewed_checkpointer

# 父目录由宿主明确创建，create=True仅新文件。
with open_reviewed_checkpointer(local_path, create=True) as saver:
    graph = build_existing_graph(gate.node, saver)
    graph.invoke(initial_state, config, durability="sync")
    ticket = gate.prepare(graph, config, summary="合成修改", ttl_seconds=300)
    save_owned_json_ticket(ticket)

# 新进程重新构造相同gate和图，重开原文件；不重新prepare。
with open_reviewed_checkpointer(local_path) as saver:
    graph = build_existing_graph(gate.node, saver)
    result = gate.resume(graph, config, load_owned_json_ticket())
```

这是宿主接入片段，完整分命令流程见 [示例](../examples/durable-graph/README.md)。gate.resume的图继续使用durability="sync"，等待当前checkpoint写入；业务结果仍留在宿主对象，不写入完成标记。初始化和恢复必须用同一thread/call、graph_id/revision、工具版本、Policy、凭证/key和保存的ticket。

## 文件和版本

只接受明确本机文件，拒绝:memory:/URI/UNC、缺父目录/目录。create=True独占创建，默认用mode=rw打开已有文件；缺失不能创建空状态。文件有Aegis本机marker格式1，记录三个框架版本与strict serializer配置；重开前核对marker和官方表列，拒绝不匹配，不自动setup/迁移或接管其他SQLite库。框架版本升级与文件迁移需另行设计。

WAL + synchronous=FULL，连接锁等待0<timeout<=5秒（默认3）；上下文退出关闭连接。JsonPlusSerializer显式禁止pickle及额外自定义类型恢复，保留官方builtin safe类型；不依赖全局环境开关。被阻止的自定义类型可能按官方行为退化为普通数据，仍受后续绑定校验，不作为可执行对象使用。

checkpoint和ticket会主动保存完整业务实参，宿主需保护目录、访问权限和备份。Windows文件创建模式不等同于ACL隔离。仅恢复可信本机文件；marker/MAC都不是防恶意宿主、数据库管理员或磁盘回滚的审计机制。不要删除未知动作对应文件、换id/key或恢复单个旧主文件来尝试再次执行。

## 退出后的行为

| 上次进程退出位置 | 新进程结果 |
| --- | --- |
| 暂停/prepare已保存，尚未领取 | 原审批未过期且批准后可以显式恢复1次 |
| claim已提交，函数尚未开始 | claimed未知；拒绝重领，工具0次 |
| 合成写入已fsync，尚未确认 | claimed未知；保留可能的部分副作用，不重复 |
| completed已提交，图继续前 | 图可能仍暂停；不能重新执行，不自动生成收据 |
| 图sync写入完成，输出前退出 | status读取完成标记；重复resume拒绝 |

真实验证由独立Python子进程及测试专用os._exit钩子完成，生产入口没有故障开关。SQLite和审批/业务存储没有共同事务，进程恢复不等于业务回滚、自动重试或外部系统恰好一次。confirmed/unknown与continuation状态沿用013；无法判断的动作需人工分别查询审批记录、checkpoint与实际业务结果。

本轮只证明本机进程退出/重启，不声称断电、损坏硬件、网络文件系统、跨版本恢复或分布式调度可靠性。正在运行的SQLite库可能依赖-wal/-shm，备份需宿主使用一致性方式，不能直接复制一个活动主文件。

验收见 [014任务](../specs/014-durable-graph/tasks.md)，取舍见 [ADR-0008](adr/0008-durable-graph.md)。
